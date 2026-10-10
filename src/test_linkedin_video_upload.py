
import os
import sys

from publish_linkedin import (
    VIDEO_FILE,
    get_member_urn,
    upload_video,
    wait_for_video,
)


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")

    if not VIDEO_FILE.is_file():
        raise FileNotFoundError(
            "linkedin_video.mp4 was not found. "
            "Download the preview artifact first."
        )

    print("Starting LinkedIn video upload-only test...")
    print(f"Video file size: {VIDEO_FILE.stat().st_size:,} bytes")

    # Reuse the already-tested LinkedIn authentication flow.
    owner_urn = get_member_urn(token)

    # Upload and finalize the media asset.
    # This does not create a LinkedIn post.
    video_urn = upload_video(VIDEO_FILE, owner_urn)

    print("Upload finalized. Waiting for LinkedIn processing...")

    # Verify that LinkedIn has made the uploaded video available.
    wait_for_video(video_urn)

    print("SUCCESS: LinkedIn accepted and processed the video.")
    print("No LinkedIn post was created.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
