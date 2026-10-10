import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
VIDEO_FILE = ROOT / "linkedin_video.mp4"
LEDGER_FILE = ROOT / "published-ledger.json"
TIME_ZONE = ZoneInfo("Asia/Kolkata")

USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
VIDEOS_URL = "https://api.linkedin.com/rest/videos"
POSTS_URL = "https://api.linkedin.com/rest/posts"

VIDEO_API_VERSION = os.getenv("LINKEDIN_VIDEO_API_VERSION", "202609")
POSTS_API_VERSION = os.getenv("LINKEDIN_POSTS_API_VERSION", "202609")


def check_response(response, operation):
    """Raise a useful error without exposing credentials."""
    if not response.ok:
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        detail = response.text[:600]
        if token:
            detail = detail.replace(token, "[REDACTED]")
        raise RuntimeError(
            f"{operation} failed (HTTP {response.status_code}): {detail}"
        )


def api_headers(version, json_body=True):
    """Build headers for LinkedIn's versioned REST APIs."""
    headers = {
        "Authorization": f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}",
        "Linkedin-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def build_commentary(data):
    """Format the post and normalize hashtags to include #."""
    post_text = data.get("post", "").strip()
    raw_hashtags = data.get("hashtags", [])

    if not isinstance(raw_hashtags, list):
        raise ValueError("The hashtags field must be a list.")

    hashtags = []
    seen = set()
    for raw_tag in raw_hashtags:
        tag = "".join(str(raw_tag).strip().lstrip("#").split())
        if not tag or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        hashtags.append(f"#{tag}")

    if hashtags:
        post_text += "\n\n" + " ".join(hashtags)
    return post_text


def get_member_urn(token):
    """Retrieve the authenticated LinkedIn member identifier."""
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


def upload_video(video_path, owner_urn):
    """Initialize, upload, and finalize a LinkedIn video."""
    file_size = video_path.stat().st_size
    if file_size < 75 * 1024:
        raise RuntimeError("The MP4 is smaller than LinkedIn's 75 KB minimum.")

    headers = api_headers(VIDEO_API_VERSION)
    initialize_response = requests.post(
        f"{VIDEOS_URL}?action=initializeUpload",
        headers=headers,
        json={
            "initializeUploadRequest": {
                "owner": owner_urn,
                "fileSizeBytes": file_size,
                "uploadCaptions": False,
                "uploadThumbnail": False,
            }
        },
        timeout=30,
    )
    check_response(initialize_response, "Initialize video upload")

    try:
        upload_data = initialize_response.json().get("value", {})
    except ValueError as exc:
        raise RuntimeError("LinkedIn returned an invalid video-upload response.") from exc

    video_urn = upload_data.get("video")
    instructions = upload_data.get("uploadInstructions", [])
    if not video_urn or not instructions:
        raise RuntimeError("LinkedIn returned incomplete upload instructions.")

    uploaded_part_ids = []
    with video_path.open("rb") as video:
        for instruction in instructions:
            first = int(instruction["firstByte"])
            last = int(instruction["lastByte"])
            upload_url = instruction["uploadUrl"]

            if first < 0 or last < first or last >= file_size:
                raise RuntimeError("LinkedIn returned an invalid video byte range.")

            video.seek(first)
            part = video.read(last - first + 1)
            if len(part) != last - first + 1:
                raise RuntimeError("Could not read the complete video part.")

            # Signed upload URLs must never be logged or exposed.
            response = requests.put(
                upload_url,
                data=part,
                headers={"Content-Type": "application/octet-stream"},
                timeout=120,
            )
            check_response(response, "Upload video part")

            etag = response.headers.get("ETag")
            if not etag:
                raise RuntimeError("LinkedIn did not return an upload ETag.")
            uploaded_part_ids.append(etag.strip('"'))

    finalize_response = requests.post(
        f"{VIDEOS_URL}?action=finalizeUpload",
        headers=headers,
        json={
            "finalizeUploadRequest": {
                "video": video_urn,
                "uploadToken": upload_data.get("uploadToken", ""),
                "uploadedPartIds": uploaded_part_ids,
            }
        },
        timeout=30,
    )
    check_response(finalize_response, "Finalize video upload")
    print("Video upload finalized successfully.")
    return video_urn


def wait_for_video(video_urn):
    """Wait for LinkedIn to finish processing the uploaded video."""
    encoded_urn = quote(video_urn, safe="")
    url = f"{VIDEOS_URL}/{encoded_urn}"
    deadline = time.time() + 180

    while time.time() < deadline:
        response = requests.get(
            url,
            headers=api_headers(VIDEO_API_VERSION),
            timeout=30,
        )
        check_response(response, "Check video processing status")

        try:
            status = response.json().get("status", "")
        except ValueError as exc:
            raise RuntimeError("LinkedIn returned an invalid video status response.") from exc

        if status == "AVAILABLE":
            print("LinkedIn video processing completed.")
            return
        if status == "PROCESSING_FAILED":
            raise RuntimeError("LinkedIn could not process this video.")

        print(f"Video status: {status or 'not reported'}; waiting...")
        time.sleep(10)

    raise RuntimeError(
        "Video processing was not confirmed within 3 minutes. "
        "Check the asset status before retrying."
    )


def publish_post(data, video_urn, owner_urn):
    """Create a public LinkedIn video post and return its ID, if provided."""
    post_text = build_commentary(data)
    if not post_text:
        raise RuntimeError("The LinkedIn post text is empty.")

    payload = {
        "author": owner_urn,
        "commentary": post_text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {"media": {"title": data["video_title"].strip(), "id": video_urn}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    response = requests.post(
        POSTS_URL,
        headers=api_headers(POSTS_API_VERSION),
        json=payload,
        timeout=30,
    )
    check_response(response, "Create LinkedIn post")

    if response.status_code != 201:
        raise RuntimeError(
            f"LinkedIn did not confirm post creation: HTTP {response.status_code}."
        )

    post_id = response.headers.get("x-restli-id")
    print("SUCCESS: LinkedIn post was published.")
    if post_id:
        print(f"Post ID: {post_id}")
    return post_id


def load_ledger():
    """Load publication state from the repository-tracked ledger."""
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
    """
    Commit the ledger to main before/after publishing.
    A remote ledger write is required before attempting a public post.
    """
    LEDGER_FILE.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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
            "Could not persist publication ledger to main. "
            "No further publishing should be attempted until the ledger is checked."
        )


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")

    if not CONTENT_FILE.exists() or not VIDEO_FILE.exists():
        raise RuntimeError(
            "content.json or linkedin_video.mp4 is missing. "
            "Generate content and the video first."
        )

    try:
        data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Could not read valid content.json.") from exc

    if not isinstance(data, dict):
        raise RuntimeError("content.json must contain a JSON object.")
    if not data.get("post") or not data.get("video_title"):
        raise RuntimeError("Generated post content is incomplete.")

    publish_enabled = (
        os.getenv("PUBLISH_TO_LINKEDIN", "false").strip().lower() == "true"
    )

    if not publish_enabled:
        print("DRY RUN: No LinkedIn API publishing calls will be made.")
        print("\nFull post preview:\n")
        print(build_commentary(data))
        print(f"\nVideo ready: {VIDEO_FILE.name}")
        print("Set PUBLISH_TO_LINKEDIN=true only to publish publicly.")
        return

    # One post per India-local calendar date. Fail closed on ambiguous attempts.
    now = datetime.now(TIME_ZONE)
    date_key = now.date().isoformat()
    ledger = load_ledger()
    existing = ledger["dates"].get(date_key)

    if existing:
        status = existing.get("status")
        if status == "published":
            print(
                f"SKIP: A LinkedIn post is already recorded for {date_key}. "
                "No upload or publishing calls were made."
            )
            return
        if status in {"publishing", "needs_review"}:
            raise RuntimeError(
                f"Publication for {date_key} is marked '{status}'. "
                "Inspect LinkedIn and the ledger before retrying to avoid a duplicate."
            )
        raise RuntimeError(
            f"Unknown publication-ledger status for {date_key}; "
            "refusing to publish until it is reviewed."
        )

    video_sha256 = hashlib.sha256(VIDEO_FILE.read_bytes()).hexdigest()
    ledger["dates"][date_key] = {
        "status": "publishing",
        "started_at": now.isoformat(timespec="seconds"),
        "topic": str(data.get("topic", ""))[:200],
        "video_title": str(data.get("video_title", ""))[:200],
        "video_sha256": video_sha256,
        "note": "Reserved before calling LinkedIn to prevent duplicate daily posts.",
    }
    persist_ledger(ledger, f"Reserve LinkedIn publication for {date_key}")
    print(f"Publication slot reserved for {date_key}.")

    try:
        owner_urn = get_member_urn(token)
        video_urn = upload_video(VIDEO_FILE, owner_urn)
        wait_for_video(video_urn)
        post_id = publish_post(data, video_urn, owner_urn)
    except Exception as exc:
        # Do not auto-retry ambiguous posting failures. Manual inspection protects
        # against a duplicate if LinkedIn created a post but the response was lost.
        ledger["dates"][date_key]["status"] = "needs_review"
        ledger["dates"][date_key]["error_type"] = type(exc).__name__
        ledger["dates"][date_key]["note"] = (
            "Workflow failed after reserving the date. Inspect LinkedIn before retrying."
        )
        try:
            persist_ledger(ledger, f"Mark LinkedIn publication for {date_key} for review")
        except Exception:
            print(
                "WARNING: Could not update the ledger after failure. "
                "The last remote status should still block duplicate publishing.",
                file=sys.stderr,
            )
        raise

    ledger["dates"][date_key]["status"] = "published"
    ledger["dates"][date_key]["published_at"] = datetime.now(TIME_ZONE).isoformat(
        timespec="seconds"
    )
    ledger["dates"][date_key]["post_id"] = post_id
    ledger["dates"][date_key]["note"] = "LinkedIn API confirmed post creation."
    persist_ledger(ledger, f"Record LinkedIn publication for {date_key}")
    print(f"Publication recorded for {date_key}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
