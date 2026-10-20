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

VIDEO_API_VERSION = os.getenv("LINKEDIN_VIDEO_API_VERSION", "202606")
POSTS_API_VERSION = os.getenv("LINKEDIN_POSTS_API_VERSION", "202609")
MIN_VIDEO_BYTES = 75 * 1024
LONGFORM_MODE = os.getenv("PUBLISH_LONGFORM", "").strip().lower() in {"1", "true", "yes"}
TARGET_MIN_VIDEO_BYTES = 300_000_000 if LONGFORM_MODE else 50_000_000
MAX_VIDEO_BYTES = 380_000_000 if LONGFORM_MODE else 70_000_000


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
    post_text = str(data.get("post", "")).replace("\u2014", ",").replace("\u2013", "-").strip()
    post_text = "\n".join(line.rstrip() for line in post_text.splitlines())
    while "\n\n\n" in post_text:
        post_text = post_text.replace("\n\n\n", "\n\n")

    raw_hashtags = data.get("hashtags", [])
    if not isinstance(raw_hashtags, list):
        raise ValueError("The hashtags field must be a list.")

    tags = []
    seen = set()
    for raw_tag in raw_hashtags[:4]:
        tag = "".join(ch for ch in str(raw_tag).strip().lstrip("#") if ch.isalnum() or ch == "_")
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            tags.append(f"#{tag}")

    if len(tags) < 3:
        raise RuntimeError("At least three relevant hashtags are required.")
    if len(post_text.split()) > 110:
        raise RuntimeError("Post body exceeds 110 words. Refusing to publish.")
    return post_text + "\n\n" + " ".join(tags)


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


def validate_video(video_path):
    if not video_path.is_file():
        raise FileNotFoundError("linkedin_video.mp4 is missing. Render the video first.")
    size_bytes = video_path.stat().st_size
    if size_bytes < MIN_VIDEO_BYTES:
        raise RuntimeError(f"Video is smaller than LinkedIn's 75 KB minimum: {size_bytes:,} bytes.")
    if size_bytes < TARGET_MIN_VIDEO_BYTES:
        raise RuntimeError(
            f"Video is below the configured high-bitrate target: {size_bytes:,} bytes; "
            f"expected at least {TARGET_MIN_VIDEO_BYTES:,} bytes."
        )
    if size_bytes > MAX_VIDEO_BYTES:
        expected_cap = "380 MB" if LONGFORM_MODE else "70 MB"
        raise RuntimeError(
            f"Video exceeds the workflow's {expected_cap} safety cap: {size_bytes:,} bytes."
        )

    if not shutil_which("ffprobe"):
        raise RuntimeError("ffprobe is unavailable. Install FFmpeg before publishing.")
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,profile,level,bit_rate",
            "-show_entries", "format=format_name,duration",
            "-of", "json", str(video_path),
        ],
        capture_output=True, text=True, check=False
    )
    if probe.returncode != 0:
        raise RuntimeError("ffprobe could not inspect the LinkedIn video.")
    metadata = json.loads(probe.stdout)
    streams = metadata.get("streams", [])
    stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    duration = float(metadata.get("format", {}).get("duration", 0))
    formats = str(metadata.get("format", {}).get("format_name", "")).split(",")
    if not stream or stream.get("codec_name") != "h264":
        raise RuntimeError("LinkedIn video must contain an H.264 video stream.")
    if stream.get("width") != 1080 or stream.get("height") != 1350:
        raise RuntimeError("LinkedIn video must use the 1080 x 1350 portrait template.")
    if "mp4" not in formats:
        raise RuntimeError("LinkedIn video must use the MP4 container.")
    if stream.get("r_frame_rate") != "24/1" or stream.get("pix_fmt") != "yuv420p":
        raise RuntimeError("LinkedIn video must retain 24 fps and the yuv420p pixel format.")
    if stream.get("profile") != "High" or stream.get("level") != 42:
        raise RuntimeError("LinkedIn video must retain the H.264 High Profile, Level 4.2 encoding.")
    try:
        video_bitrate = int(stream.get("bit_rate") or 0)
    except (TypeError, ValueError):
        video_bitrate = 0
    if not 25_000_000 <= video_bitrate <= 31_000_000:
        raise RuntimeError(f"LinkedIn video bitrate must remain near 30 Mbps; got {video_bitrate:,} bps.")
    if any(s.get("codec_type") == "audio" for s in streams):
        raise RuntimeError("LinkedIn video must remain silent, without an audio track.")
    if LONGFORM_MODE:
        if not 89.5 <= duration <= 90.5:
            raise RuntimeError(f"Long-form video must be 90 seconds; got {duration:.2f}s.")
    elif not 15.5 <= duration <= 16.2:
        raise RuntimeError(f"LinkedIn video duration must remain near 15.9 seconds; got {duration:.2f}s.")


def shutil_which(program):
    import shutil
    return shutil.which(program)


def upload_video(video_path, owner_urn):
    """Register, upload chunks, and finalize one video asset on LinkedIn."""
    validate_video(video_path)
    file_size = video_path.stat().st_size

    init_response = requests.post(
        f"{VIDEOS_URL}?action=initializeUpload",
        headers=api_headers(VIDEO_API_VERSION),
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
    check_response(init_response, "Initialize LinkedIn video upload")

    try:
        upload_data = init_response.json().get("value", {})
    except ValueError as exc:
        raise RuntimeError("LinkedIn returned invalid video-upload instructions.") from exc

    video_urn = upload_data.get("video")
    instructions = upload_data.get("uploadInstructions", [])
    if not video_urn or not video_urn.startswith("urn:li:video:") or not instructions:
        raise RuntimeError("LinkedIn returned incomplete video-upload instructions.")

    uploaded_part_ids = []
    with video_path.open("rb") as video:
        for instruction in instructions:
            first = int(instruction["firstByte"])
            last = int(instruction["lastByte"])
            upload_url = instruction["uploadUrl"]
            video.seek(first)
            part = video.read(last - first + 1)
            if not part:
                raise RuntimeError("LinkedIn requested an empty video part.")

            response = requests.put(
                upload_url,
                data=part,
                headers={"Content-Type": "application/octet-stream"},
                timeout=120,
            )
            check_response(response, "Upload LinkedIn video part")
            etag = response.headers.get("ETag")
            if not etag:
                raise RuntimeError("LinkedIn did not return an ETag for an uploaded part.")
            uploaded_part_ids.append(etag.strip('"'))

    finalize_response = requests.post(
        f"{VIDEOS_URL}?action=finalizeUpload",
        headers=api_headers(VIDEO_API_VERSION),
        json={
            "finalizeUploadRequest": {
                "video": video_urn,
                "uploadToken": upload_data.get("uploadToken", ""),
                "uploadedPartIds": uploaded_part_ids,
            }
        },
        timeout=30,
    )
    check_response(finalize_response, "Finalize LinkedIn video upload")
    print("LinkedIn video upload finalized.")
    return video_urn


def wait_for_video(video_urn):
    encoded_urn = quote(video_urn, safe="")
    url = f"{VIDEOS_URL}/{encoded_urn}"
    deadline = time.time() + 240

    while time.time() < deadline:
        response = requests.get(
            url,
            headers=api_headers(VIDEO_API_VERSION, json_body=False),
            timeout=30,
        )
        check_response(response, "Check LinkedIn video processing")
        try:
            status = response.json().get("status", "")
        except ValueError as exc:
            raise RuntimeError("LinkedIn returned invalid video-processing status.") from exc

        if status == "AVAILABLE":
            print("LinkedIn video processing completed.")
            return
        if status == "PROCESSING_FAILED":
            raise RuntimeError("LinkedIn could not process the uploaded video.")
        print(f"Video status: {status or 'not reported'}; waiting...")
        time.sleep(10)

    raise RuntimeError(
        "LinkedIn processing was not confirmed within four minutes. "
        "Check the asset status before retrying."
    )


def publish_post(data, video_urn, owner_urn):
    commentary = build_commentary(data)
    title = str(data.get("video_title", data.get("topic", ""))).strip()[:200]
    if not title:
        raise RuntimeError("Video title is missing.")

    payload = {
        "author": owner_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "title": title,
                "id": video_urn,
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = requests.post(
        POSTS_URL,
        headers=api_headers(POSTS_API_VERSION),
        json=payload,
        timeout=30,
    )
    check_response(response, "Create LinkedIn video post")
    if response.status_code != 201:
        raise RuntimeError(f"LinkedIn did not confirm post creation: HTTP {response.status_code}.")

    post_id = response.headers.get("x-restli-id")
    print("SUCCESS: LinkedIn video post was published.")
    if post_id:
        print(f"Post ID: {post_id}")
    return post_id


def sha256_file(file_path, chunk_size=1024 * 1024):
    """Hash a potentially large video without loading the entire file into memory."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
            raise RuntimeError("Could not stage the publication ledger; refusing to publish.")

    commit = git(["commit", "-m", message])
    if commit.returncode != 0:
        raise RuntimeError("Could not commit the publication ledger; refusing to publish.")
    push = git(["push", "origin", "HEAD:main"])
    if push.returncode != 0:
        raise RuntimeError("Could not persist the publication ledger to main. Check it before retrying.")


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")
    if not CONTENT_FILE.is_file() or not VIDEO_FILE.is_file():
        raise RuntimeError("content.json or linkedin_video.mp4 is missing. Generate both first.")

    try:
        data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Could not read valid content.json.") from exc
    if not isinstance(data, dict) or not data.get("topic") or not data.get("post"):
        raise RuntimeError("Generated post content is incomplete.")
    expected_slide_count = 10 if LONGFORM_MODE else 5
    if not data.get("video_title") or not isinstance(data.get("slides"), list) or len(data["slides"]) != expected_slide_count:
        raise RuntimeError(f"A video title and exactly {expected_slide_count} validated slides are required.")

    validate_video(VIDEO_FILE)
    publish_enabled = os.getenv("PUBLISH_TO_LINKEDIN", "false").strip().lower() == "true"
    if not publish_enabled:
        print("DRY RUN: No LinkedIn API upload or publishing calls will be made.")
        print("\nPost preview:\n")
        print(build_commentary(data))
        print(f"\nVideo ready: {VIDEO_FILE.name}")
        print("Video format: 1080 x 1350 MP4, H.264, 24 fps, 4:5 portrait")
        print("Set PUBLISH_TO_LINKEDIN=true only for a scheduled public post.")
        return

    now = datetime.now(TIME_ZONE)
    request_id = os.getenv("PUBLISH_REQUEST_ID", "").strip()
    publish_intent = os.getenv("PUBLISH_INTENT", "scheduled").strip().lower()
    is_correction = publish_intent == "correction"
    is_extra = publish_intent == "extra"
    is_extra_override = publish_intent == "extra_override"
    is_longform = publish_intent == "longform"
    is_reformat = publish_intent == "reformat"
    is_plan_extra = publish_intent == "plan_extra"
    if publish_intent in {"correction", "extra", "extra_override", "reformat", "plan_extra"} and not request_id.isdigit():
        raise RuntimeError("A numeric PUBLISH_REQUEST_ID is required for correction, extra, reformat, or planned-extra publication.")
    if request_id:
        if not request_id.isdigit():
            raise RuntimeError("PUBLISH_REQUEST_ID must be a numeric GitHub issue number.")
        suffix = "correction" if is_correction else "extra" if is_extra else "extra-override" if is_extra_override else "reformat" if is_reformat else "plan-extra" if is_plan_extra else "request"
        date_key = f"{now.date().isoformat()}-{suffix}-{request_id}"
    else:
        if is_correction:
            raise RuntimeError("A numeric PUBLISH_REQUEST_ID is required for correction publication.")
        date_key = now.date().isoformat()

    ledger = load_ledger()
    existing = ledger["dates"].get(date_key)
    daily_key = now.date().isoformat()
    request_prefix = f"{daily_key}-request-"
    correction_prefix = f"{daily_key}-correction-"

    # Ordinary runs may publish only once per India-local date. A specifically
    # titled owner-triggered correction request is the sole exception, and is
    # limited to one correction attempt after a confirmed original post.
    daily_slot = ledger["dates"].get(daily_key)
    if is_plan_extra:
        requested_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
        expected_topic = {"6": "Making chart components easier to extend"}.get(requested_day)
        if expected_topic is None or data.get("topic") != expected_topic:
            raise RuntimeError("Planned-extra publication is restricted to the verified Day 6 topic.")
        day_records = [
            (key, value) for key, value in ledger["dates"].items()
            if key == daily_key or key.startswith(f"{daily_key}-")
        ]
        baseline_published = any(
            isinstance(value, dict) and value.get("status") == "published"
            and "-plan-extra-" not in key and value.get("topic") != expected_topic
            for key, value in day_records
        )
        if not baseline_published:
            raise RuntimeError("A Day 6 extra post requires a confirmed publication earlier today.")
        uncertain = [
            key for key, value in day_records
            if isinstance(value, dict) and value.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before proceeding."
            )
        prior_day6 = [
            key for key, value in ledger["dates"].items()
            if (key == daily_key or key.startswith(f"{daily_key}-"))
            and isinstance(value, dict)
            and value.get("topic") == expected_topic
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_day6:
            raise RuntimeError("Day 6 already has a published or uncertain publication record today.")
    elif is_reformat:
        requested_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
        expected_topic = {
            "5": "Debugging TypeScript and chart rendering issues",
        }.get(requested_day)
        if expected_topic is None or data.get("topic") != expected_topic:
            raise RuntimeError("Reformat publication is restricted to the verified Day 5 topic.")
        day_records = [
            (key, value) for key, value in ledger["dates"].items()
            if key == daily_key or key.startswith(f"{daily_key}-")
        ]
        baseline_published = any(
            isinstance(value, dict)
            and value.get("status") == "published"
            and value.get("topic") == expected_topic
            and "-reformat-" not in key
            for key, value in day_records
        )
        if not baseline_published:
            raise RuntimeError("A reformat requires today's confirmed original Day 5 post.")
        uncertain = [
            key for key, value in day_records
            if isinstance(value, dict) and value.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before reformatting."
            )
        prior_reformats = [
            key for key, value in ledger["dates"].items()
            if key.startswith(f"{daily_key}-reformat-") and key != date_key
            and isinstance(value, dict)
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_reformats:
            raise RuntimeError("A reformatted LinkedIn post was already attempted today. Refusing another.")
    elif is_extra:
        requested_extra_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
        extra_topics = {
            "3": "Why I created reusable chart utilities in common.ts",
            "5": "Debugging TypeScript and chart rendering issues",
            "99": "Binary Search in C++: Iterative and Recursive",
            "100": "Java Polymorphism: Reference Type vs Runtime Object",
        }
        expected_topic = extra_topics.get(requested_extra_day)
        if expected_topic is None:
            raise RuntimeError(
                "Extra publication is allowed only for explicitly supported content-plan days (3, 5, 99, or 100)."
            )
        if data.get("topic") != expected_topic:
            raise RuntimeError(
                f"Day {requested_extra_day} extra publication must use the exact planned topic: {expected_topic!r}."
            )
        day_records = [
            (key, value) for key, value in ledger["dates"].items()
            if key == daily_key or key.startswith(f"{daily_key}-")
        ]
        baseline_published = any(
            value.get("status") == "published" and not key.startswith(f"{daily_key}-extra-")
            for key, value in day_records if isinstance(value, dict)
        )
        if not baseline_published:
            raise RuntimeError("An extra post requires a previously confirmed publication today.")
        uncertain = [
            key for key, value in day_records
            if isinstance(value, dict) and value.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before publishing an extra post."
            )
        prior_extras = [
            key for key, value in ledger["dates"].items()
            if key.startswith(f"{daily_key}-extra-") and key != date_key
            and isinstance(value, dict)
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_extras:
            raise RuntimeError("An extra LinkedIn post was already attempted today. Refusing another.")
    elif is_extra_override:
        requested_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
        expected_topic = {"14": "Connecting Truloop's interface to backend APIs"}.get(requested_day)
        if expected_topic is None or data.get("topic") != expected_topic:
            raise RuntimeError("Same-day override is restricted to the verified Day 14 API-integration topic.")
        day_records = [
            (key, value) for key, value in ledger["dates"].items()
            if key == daily_key or key.startswith(f"{daily_key}-")
        ]
        baseline_published = any(
            isinstance(value, dict)
            and value.get("status") == "published"
            and not key.startswith(f"{daily_key}-extra-override-")
            for key, value in day_records
        )
        if not baseline_published:
            raise RuntimeError("Same-day override requires a previously confirmed publication today.")
        uncertain = [
            key for key, value in day_records
            if isinstance(value, dict) and value.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before publishing another post."
            )
        prior_overrides = [
            key for key, value in ledger["dates"].items()
            if key.startswith(f"{daily_key}-extra-override-") and key != date_key
            and isinstance(value, dict)
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_overrides:
            raise RuntimeError("A same-day override post was already attempted today. Refusing another.")
    elif is_correction:
        day_records = [
            (key, value) for key, value in ledger["dates"].items()
            if key == daily_key or key.startswith(f"{daily_key}-")
        ]
        baseline_published = any(
            value.get("status") == "published" and not key.startswith(correction_prefix)
            for key, value in day_records if isinstance(value, dict)
        )
        if not baseline_published:
            raise RuntimeError("A corrected post requires today's original post to be confirmed published.")
        uncertain = [
            key for key, value in day_records
            if isinstance(value, dict) and value.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before correcting."
            )
        prior_corrections = [
            key for key, value in ledger["dates"].items()
            if key.startswith(correction_prefix) and key != date_key
            and isinstance(value, dict)
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_corrections:
            raise RuntimeError("A corrected video was already attempted today. Refusing another correction post.")
    elif request_id:
        if isinstance(daily_slot, dict) and daily_slot.get("status") in {
            "published", "publishing", "needs_review"
        }:
            raise RuntimeError(
                "A scheduled/daily LinkedIn publication already exists or was attempted today. "
                "Inspect LinkedIn and the ledger before requesting another."
            )

        prior_requests = [
            (key, value) for key, value in ledger["dates"].items()
            if key.startswith(request_prefix)
            and key != date_key
            and isinstance(value, dict)
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_requests:
            raise RuntimeError(
                "A one-off LinkedIn post has already been attempted today. "
                "Inspect LinkedIn and the ledger before requesting another."
            )
    else:
        prior_requests = [
            value for key, value in ledger["dates"].items()
            if key.startswith(request_prefix)
            and isinstance(value, dict)
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_requests:
            statuses = {value.get("status") for value in prior_requests}
            if "published" in statuses:
                print(
                    "SKIP: A one-off LinkedIn post is already recorded for today's India-local date. "
                    "Refusing to publish a second post."
                )
                return
            raise RuntimeError(
                "A one-off LinkedIn publication was attempted today and is not safely confirmed. "
                "Inspect LinkedIn and the ledger before retrying."
            )

    if existing:
        status = existing.get("status")
        if status == "published":
            print(f"SKIP: A LinkedIn post is already recorded for {date_key}.")
            return
        if status in {"publishing", "needs_review"}:
            raise RuntimeError(
                f"Publication for {date_key} is marked '{status}'. Inspect LinkedIn and the ledger before retrying."
            )
        raise RuntimeError(f"Unknown publication-ledger status for {date_key}; refusing to publish.")

    video_hash = sha256_file(VIDEO_FILE)
    ledger["dates"][date_key] = {
        "status": "publishing",
        "started_at": now.isoformat(timespec="seconds"),
        "topic": str(data["topic"])[:200],
        "video_sha256": video_hash,
        "video_size_bytes": VIDEO_FILE.stat().st_size,
        "video_dimensions": "1080x1350",
        "note": "Reserved before upload to prevent duplicate daily posts.",
    }
    persist_ledger(ledger, f"Reserve LinkedIn video publication for {date_key}")
    print(f"Publication slot reserved for {date_key}.")

    try:
        owner_urn = get_member_urn(token)
        video_urn = upload_video(VIDEO_FILE, owner_urn)
        wait_for_video(video_urn)
        post_id = publish_post(data, video_urn, owner_urn)
    except Exception as exc:
        ledger["dates"][date_key]["status"] = "needs_review"
        ledger["dates"][date_key]["error_type"] = type(exc).__name__
        ledger["dates"][date_key]["note"] = "Workflow failed after reserving the date. Inspect LinkedIn before retrying."
        try:
            persist_ledger(ledger, f"Mark LinkedIn video publication for {date_key} for review")
        except Exception:
            print("WARNING: Could not update ledger after failure. Inspect repository state before retrying.", file=sys.stderr)
        raise

    ledger["dates"][date_key]["status"] = "published"
    ledger["dates"][date_key]["published_at"] = datetime.now(TIME_ZONE).isoformat(timespec="seconds")
    ledger["dates"][date_key]["post_id"] = post_id
    ledger["dates"][date_key]["video_urn"] = video_urn
    ledger["dates"][date_key]["note"] = "LinkedIn API confirmed video-post creation."
    persist_ledger(ledger, f"Record LinkedIn video publication for {date_key}")
    print(f"Publication recorded for {date_key}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
