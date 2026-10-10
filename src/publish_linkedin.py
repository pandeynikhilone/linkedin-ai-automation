
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
    if not response.ok:
        # Do not print authorization headers or token values.
        detail = response.text[:600].replace(
            os.getenv("LINKEDIN_ACCESS_TOKEN", ""),
            "[REDACTED]",
        )
        raise RuntimeError(
            f"{operation} failed (HTTP {response.status_code}): {detail}"
        )


def api_headers(version, json_body=True):
    headers = {
        "Authorization": f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}",
        "Linkedin-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    if json_body:
        headers["Content-Type"] = "application/json"

    return headers


def get_member_urn(token):
    response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    check_response(response, "LinkedIn profile lookup")

    profile = response.json()
    member_id = profile.get("sub")

    if not member_id:
        raise RuntimeError("LinkedIn did not return a member identifier.")

    return f"urn:li:person:{member_id}"


def upload_video(video_path, owner_urn, token):
    file_size = video_path.stat().st_size

    # LinkedIn's standard feed video specifications require at least 75 KB.
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

    upload_data = initialize_response.json().get("value", {})
    video_urn = upload_data.get("video")
    instructions = upload_data.get("uploadInstructions", [])

    if not video_urn or not instructions:
        raise RuntimeError("LinkedIn returned incomplete upload instructions.")

    # Use the byte ranges provided by LinkedIn; never log signed upload URLs.
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
    # LinkedIn processes uploaded media asynchronously.
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

        status = response.json().get("status", "")

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
    hashtags = data.get("hashtags", [])
    post_text = data["post"].strip()

    if hashtags:
        post_text += "\n\n" + " ".join(hashtags)

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
                "title": data["video_title"],
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
            f"Unexpected post-creation status: HTTP {response.status_code}."
        )

    post_id = response.headers.get("x-restli-id")
    print("SUCCESS: LinkedIn post was published.")
    if post_id:
        print(f"Post ID: {post_id}")


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")

    if not CONTENT_FILE.exists() or not VIDEO_FILE.exists():
        raise RuntimeError(
            "content.json or linkedin_video.mp4 is missing. "
            "Generate content and the video first."
        )

    data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))

    if not data.get("post") or not data.get("video_title"):
        raise RuntimeError("Generated post content is incomplete.")

    # Default to preview-only. Public posting requires explicit opt-in.
    publish_enabled = os.getenv("PUBLISH_TO_LINKEDIN", "false").lower()
    if publish_enabled != "true":
        print("DRY RUN: No LinkedIn API publishing calls will be made.")
        print("\nPost preview:\n")
        print(data["post"])
        print("\nHashtags:", " ".join(data.get("hashtags", [])))
        print(f"\nVideo ready: {VIDEO_FILE.name}")
        print("Set PUBLISH_TO_LINKEDIN=true only to publish publicly.")
        return

    owner_urn = get_member_urn(token)
    video_urn = upload_video(VIDEO_FILE, owner_urn, token)
    wait_for_video(video_urn)
    publish_post(data, video_urn, owner_urn)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
