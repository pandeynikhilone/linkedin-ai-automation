import os
import sys
from pathlib import Path

from publish_linkedin import IMAGE_FILE, get_member_urn, upload_image, validate_image


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN is missing.")

    if not IMAGE_FILE.is_file():
        raise FileNotFoundError(
            "linkedin_image.jpg was not found. Download the linkedin-illustrated-content artifact first."
        )

    validate_image(IMAGE_FILE)
    print("Starting LinkedIn image upload-only test.")
    print(f"Image file size: {IMAGE_FILE.stat().st_size:,} bytes")

    owner_urn = get_member_urn(token)
    image_urn = upload_image(IMAGE_FILE, owner_urn)

    print("SUCCESS: LinkedIn accepted the image upload.")
    print(f"Image URN: {image_urn}")
    print("No LinkedIn post was created.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
