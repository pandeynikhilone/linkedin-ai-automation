import os
import sys

from publish_linkedin import VIDEO_FILE, get_member_urn, upload_video, wait_for_video


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")
    if not VIDEO_FILE.is_file():
        raise FileNotFoundError(
            "linkedin_video.mp4 was not found. Download the linkedin-video-content artifact first."
        )

    print("Starting LinkedIn video upload-only test.")
    print(f"Video file size: {VIDEO_FILE.stat().st_size:,} bytes")
    owner_urn = get_member_urn(token)
    video_urn = upload_video(VIDEO_FILE, owner_urn)
    print("Upload finalized. Waiting for LinkedIn processing...")
    wait_for_video(video_urn)
    print("SUCCESS: LinkedIn accepted and processed the video.")
    print(f"Video URN: {video_urn}")
    print("No LinkedIn post was created.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
