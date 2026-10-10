import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
IMAGE_FILE = ROOT / "linkedin_image.jpg"
LEDGER_FILE = ROOT / "published-ledger.json"
TIME_ZONE = ZoneInfo("Asia/Kolkata")

USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
IMAGES_URL = "https://api.linkedin.com/rest/images"
POSTS_URL = "https://api.linkedin.com/rest/posts"

IMAGES_API_VERSION = os.getenv("LINKEDIN_IMAGES_API_VERSION", "202609")
POSTS_API_VERSION = os.getenv("LINKEDIN_POSTS_API_VERSION", "202609")
MAX_IMAGE_BYTES = 12 * 1024 * 1024


def check_response(response, operation):
    if not response.ok:
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        detail = response.text[:600]
        if token:
            detail = detail.replace(token, "[REDACTED]")
        raise RuntimeError(f"{operation} failed (HTTP {response.status_code}): {detail}")


def api_headers(version, json_body=True):
    headers = {
        "Authorization": f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}",
        "Linkedin-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def build_commentary(data):
    """Keep the post concise, preserve line breaks, and append separate hashtags."""
    post_text = str(data.get("post", "")).replace("\u2014", ",").replace("\u2013", "-").strip()
    post_text = "\n".join(line.rstrip() for line in post_text.splitlines())
    while "\n\n\n" in post_text:
        post_text = post_text.replace("\n\n\n", "\n\n")

    raw_hashtags = data.get("hashtags", [])
    if not isinstance(raw_hashtags, list):
        raise ValueError("The hashtags field must be a list.")

    hashtags = []
    seen = set()
    for raw_tag in raw_hashtags[:4]:
        tag = "".join(
            char for char in str(raw_tag).strip().lstrip("#")
            if char.isalnum() or char == "_"
        )
        if not tag or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        hashtags.append(f"#{tag}")

    if len(hashtags) < 3:
        raise RuntimeError("At least three relevant hashtags are required.")
    if len(post_text.split()) > 110:
        raise RuntimeError("Post body exceeds 110 words. Refusing to publish oversized copy.")

    return post_text + "\n\n" + " ".join(hashtags)


def get_member_urn(token):
    response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    check_response(response, "LinkedIn profile lookup")
    try:
        profile = response.json()
    except ValueError as exc:
        raise RuntimeError("LinkedIn returned an invalid profile response.") from exc

    member_id = profile.get("sub")
    if not member_id:
        raise RuntimeError("LinkedIn did not return a member identifier.")
    return f"urn:li:person:{member_id}"


def validate_image(image_path):
    if not image_path.is_file():
        raise FileNotFoundError("linkedin_image.jpg is missing. Generate the illustration first.")
    size_bytes = image_path.stat().st_size
    if size_bytes < 100 * 1024 or size_bytes > MAX_IMAGE_BYTES:
        raise RuntimeError(f"Image size is outside the expected range: {size_bytes:,} bytes.")

    try:
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            if image.format != "JPEG" or image.size != (2048, 2048):
                raise RuntimeError("Image must be a 2048 x 2048 pixel JPEG.")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("The generated file is not a valid JPEG.") from exc


def upload_image(image_path, owner_urn):
    """Register and upload one image using LinkedIn's Images API."""
    validate_image(image_path)
    init_response = requests.post(
        f"{IMAGES_URL}?action=initializeUpload",
        headers=api_headers(IMAGES_API_VERSION),
        json={"initializeUploadRequest": {"owner": owner_urn}},
        timeout=30,
    )
    check_response(init_response, "Initialize LinkedIn image upload")

    try:
        value = init_response.json().get("value", {})
    except ValueError as exc:
        raise RuntimeError("LinkedIn returned an invalid image-upload response.") from exc

    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")
    if not upload_url or not image_urn or not image_urn.startswith("urn:li:image:"):
        raise RuntimeError("LinkedIn returned incomplete image-upload instructions.")

    # The upload URL is signed. Do not log or persist it.
    with image_path.open("rb") as image_file:
        upload_response = requests.put(
            upload_url,
            data=image_file,
            headers={"Content-Type": "application/octet-stream"},
            timeout=120,
        )
    check_response(upload_response, "Upload LinkedIn image")
    print("Image uploaded to LinkedIn.")
    return image_urn


def publish_post(data, image_urn, owner_urn):
    """Publish an image and its commentary as one public LinkedIn post."""
    commentary = build_commentary(data)
    if not commentary:
        raise RuntimeError("The LinkedIn post text is empty.")

    payload = {
        "author": owner_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {"media": {"id": image_urn}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = requests.post(
        POSTS_URL,
        headers=api_headers(POSTS_API_VERSION),
        json=payload,
        timeout=30,
    )
    check_response(response, "Create LinkedIn image post")

    if response.status_code != 201:
        raise RuntimeError(f"LinkedIn did not confirm post creation: HTTP {response.status_code}.")

    post_id = response.headers.get("x-restli-id")
    print("SUCCESS: LinkedIn image post was published.")
    if post_id:
        print(f"Post ID: {post_id}")
    return post_id


def load_ledger():
    if not LEDGER_FILE.exists():
        return {"timezone": "Asia/Kolkata", "dates": {}}
    try:
        ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Could not read published-ledger.json safely.") from exc
    if not isinstance(ledger, dict) or not isinstance(ledger.get("dates"), dict):
        raise RuntimeError("published-ledger.json has an unexpected structure.")
    return ledger


def persist_ledger(ledger, message):
    """Commit the publication ledger before and after posting to prevent duplicates."""
    LEDGER_FILE.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def git(args):
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    for args in (
        ["config", "user.name", "github-actions[bot]"],
        ["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        ["add", "published-ledger.json"],
    ):
        result = git(args)
        if result.returncode != 0:
            raise RuntimeError("Could not stage publication ledger; refusing to publish.")

    commit = git(["commit", "-m", message])
    if commit.returncode != 0:
        raise RuntimeError("Could not commit publication ledger; refusing to publish.")

    push = git(["push", "origin", "HEAD:main"])
    if push.returncode != 0:
        raise RuntimeError(
            "Could not persist publication ledger to main. Check it before retrying."
        )


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")
    if not CONTENT_FILE.is_file() or not IMAGE_FILE.is_file():
        raise RuntimeError("content.json or linkedin_image.jpg is missing. Generate both first.")

    try:
        data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Could not read valid content.json.") from exc

    if not isinstance(data, dict) or not data.get("topic") or not data.get("post"):
        raise RuntimeError("Generated post content is incomplete.")
    if not data.get("illustration_brief") or not data.get("source_facts"):
        raise RuntimeError("The illustration brief and verified source facts are required.")

    validate_image(IMAGE_FILE)
    publish_enabled = os.getenv("PUBLISH_TO_LINKEDIN", "false").strip().lower() == "true"

    if not publish_enabled:
        print("DRY RUN: No LinkedIn API upload or publishing calls will be made.")
        print("\nPost preview:\n")
        print(build_commentary(data))
        print(f"\nImage ready: {IMAGE_FILE.name}")
        print("Dimensions: 2048 x 2048 pixels, square JPEG")
        print("Set PUBLISH_TO_LINKEDIN=true only for a scheduled public post.")
        return

    now = datetime.now(TIME_ZONE)
    request_id = os.getenv("PUBLISH_REQUEST_ID", "").strip()
    if request_id:
        if not request_id.isdigit():
            raise RuntimeError("PUBLISH_REQUEST_ID must be a numeric GitHub issue number.")
        # A user-requested one-off post can coexist with the daily scheduled post.
        # The same issue ID remains idempotent, so retries cannot publish it twice.
        date_key = f"{now.date().isoformat()}-request-{request_id}"
    else:
        date_key = now.date().isoformat()
    ledger = load_ledger()
    existing = ledger["dates"].get(date_key)

    if existing:
        status = existing.get("status")
        if status == "published":
            print(f"SKIP: A LinkedIn post is already recorded for {date_key}.")
            return
        if status in {"publishing", "needs_review"}:
            raise RuntimeError(
                f"Publication for {date_key} is marked '{status}'. "
                "Inspect LinkedIn and the ledger before retrying."
            )
        raise RuntimeError(f"Unknown publication-ledger status for {date_key}; refusing to publish.")

    image_sha256 = hashlib.sha256(IMAGE_FILE.read_bytes()).hexdigest()
    ledger["dates"][date_key] = {
        "status": "publishing",
        "started_at": now.isoformat(timespec="seconds"),
        "topic": str(data.get("topic", ""))[:200],
        "image_sha256": image_sha256,
        "image_size": "2048x2048",
        "note": "Reserved before calling LinkedIn to prevent duplicate daily posts.",
    }
    persist_ledger(ledger, f"Reserve LinkedIn image publication for {date_key}")
    print(f"Publication slot reserved for {date_key}.")

    try:
        owner_urn = get_member_urn(token)
        image_urn = upload_image(IMAGE_FILE, owner_urn)
        post_id = publish_post(data, image_urn, owner_urn)
    except Exception as exc:
        ledger["dates"][date_key]["status"] = "needs_review"
        ledger["dates"][date_key]["error_type"] = type(exc).__name__
        ledger["dates"][date_key]["note"] = (
            "Workflow failed after reserving the date. Inspect LinkedIn before retrying."
        )
        try:
            persist_ledger(ledger, f"Mark LinkedIn image publication for {date_key} for review")
        except Exception:
            print(
                "WARNING: Could not update ledger after failure. Inspect repository state before retrying.",
                file=sys.stderr,
            )
        raise

    ledger["dates"][date_key]["status"] = "published"
    ledger["dates"][date_key]["published_at"] = datetime.now(TIME_ZONE).isoformat(timespec="seconds")
    ledger["dates"][date_key]["post_id"] = post_id
    ledger["dates"][date_key]["image_urn"] = image_urn
    ledger["dates"][date_key]["note"] = "LinkedIn API confirmed image-post creation."
    persist_ledger(ledger, f"Record LinkedIn image publication for {date_key}")
    print(f"Publication recorded for {date_key}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
