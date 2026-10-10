
import os
import sys
import requests


USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")

    if not token:
        raise RuntimeError(
            "LINKEDIN_ACCESS_TOKEN is missing from GitHub Actions secrets."
        )

    response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )

    if response.status_code == 401:
        raise RuntimeError(
            "LinkedIn rejected the token. Check that it was saved correctly "
            "and has not expired."
        )

    if response.status_code == 403:
        raise RuntimeError(
            "LinkedIn denied the request. Check the granted OpenID Connect "
            "permissions and app authorization."
        )

    if not response.ok:
        raise RuntimeError(
            f"LinkedIn returned HTTP {response.status_code}. "
            "Check the workflow log and app configuration."
        )

    try:
        profile = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "LinkedIn returned an unexpected response."
        ) from exc

    if not isinstance(profile, dict) or not profile.get("sub"):
        raise RuntimeError(
            "Authentication responded, but the member identifier was absent."
        )

    # Do not print profile data, email, or the access token to workflow logs.
    print("SUCCESS: LinkedIn authentication works.")
    print("SUCCESS: A member identifier was returned.")
    print("No LinkedIn posts were created or changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
