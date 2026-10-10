import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
VIDEO_FILE = ROOT / "linkedin_video.mp4"

USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
VIDEOS_URL = "https://api.linkedin.com/rest/videos"
POSTS_URL = "https://api.linkedin.com/rest/posts"

VIDEO_API_VERSION = os.getenv("LINKEDIN_VIDEO_API_VERSION", "202606")
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
        "Authorization": (
            f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}"
        ),
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
        # Handle tags with or without an existing # prefix.
        tag = str(raw_tag).strip().lstrip("#")
        tag = "".join(tag.split())

        if not tag:
            continue

        # Avoid duplicate hashtags.
        if tag.casefold() in seen:
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
        raise RuntimeError(
            "LinkedIn returned an invalid profile response."
        ) from exc

    member_id = profile.get("sub")

    if not member_id:
        raise RuntimeError(
            "LinkedIn did not return a member identifier."
        )

    return f"urn:li:person:{member_id}"


def upload_video(video_path, owner_urn):
    """Initialize, upload, and finalize a LinkedIn video."""
    file_size = video_path.stat().st_size

    if file_size < 75 * 1024:
        raise RuntimeError(
            "The MP4 is smaller than LinkedIn's 75 KB minimum."
        )

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
        raise RuntimeError(
            "LinkedIn returned an invalid video-upload response."
        ) from exc

    video_urn = upload_data.get("video")
    instructions = upload_data.get("uploadInstructions", [])

    if not video_urn or not instructions:
        raise RuntimeError(
            "LinkedIn returned incomplete upload instructions."
        )

    uploaded_part_ids = []

    # LinkedIn provides inclusive firstByte/lastByte ranges.
    with video_path.open("rb") as video:
        for instruction in instructions:
            first = int(instruction["firstByte"])
            last = int(instruction["lastByte"])
            upload_url = instruction["uploadUrl"]

            if first < 0 or last < first or last >= file_size:
                raise RuntimeError(
                    "LinkedIn returned an invalid video byte range."
                )

            video.seek(first)
            part = video.read(last - first + 1)

            if len(part) != last - first + 1:
                raise RuntimeError(
                    "Could not read the complete video part."
                )

            # This is a signed upload URL. Do not log it or expose it.
            response = requests.put(
                upload_url,
                data=part,
                headers={
                    "Content-Type": "application/octet-stream"
                },
                timeout=120,
            )
            check_response(response, "Upload video part")

            etag = response.headers.get("ETag")

            if not etag:
                raise RuntimeError(
                    "LinkedIn did not return an upload ETag."
                )

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
            raise RuntimeError(
                "LinkedIn returned an invalid video status response."
            ) from exc

        if status == "AVAILABLE":
            print("LinkedIn video processing completed.")
            return

        if status == "PROCESSING_FAILED":
            raise RuntimeError(
                "LinkedIn could not process this video."
            )

        print(
            f"Video status: {status or 'not reported'}; waiting..."
        )
        time.sleep(10)

    raise RuntimeError(
        "Video processing was not confirmed within 3 minutes. "
        "Check the asset status before retrying."
    )


def publish_post(data, video_urn, owner_urn):
    """Create a public LinkedIn video post."""
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
        "content": {
            "media": {
                "title": data["video_title"].strip(),
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
    check_response(response, "Create LinkedIn post")

    if response.status_code != 201:
        raise RuntimeError(
            "LinkedIn did not confirm post creation: "
            f"HTTP {response.status_code}."
        )

    post_id = response.headers.get("x-restli-id")

    print("SUCCESS: LinkedIn post was published.")

    if post_id:
        print(f"Post ID: {post_id}")


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not token:
        raise RuntimeError(
            "LINKEDIN_ACCESS_TOKEN is missing."
        )

    if not CONTENT_FILE.exists():
        raise FileNotFoundError(
            "content.json is missing. Generate content first."
        )

    if not VIDEO_FILE.exists():
        raise FileNotFoundError(
            "linkedin_video.mp4 is missing. Generate the video first."
        )

    try:
        data = json.loads(
            CONTENT_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            "Could not read valid content.json."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "content.json must contain a JSON object."
        )

    if not data.get("post") or not data.get("video_title"):
        raise RuntimeError(
            "Generated post content is incomplete."
        )

    # Default to preview-only. Public publishing requires explicit opt-in.
    publish_enabled = (
        os.getenv("PUBLISH_TO_LINKEDIN", "false").strip().lower()
        == "true"
    )

    if not publish_enabled:
        print("DRY RUN: No LinkedIn API publishing calls will be made.")
        print("\nFull post preview:\n")
        print(build_commentary(data))
        print(f"\nVideo ready: {VIDEO_FILE.name}")
        print("Set PUBLISH_TO_LINKEDIN=true only to publish publicly.")
        return

    print("Public publishing is enabled.")

    owner_urn = get_member_urn(token)
    video_urn = upload_video(VIDEO_FILE, owner_urn)
    wait_for_video(video_urn)
    publish_post(data, video_urn, owner_urn)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
