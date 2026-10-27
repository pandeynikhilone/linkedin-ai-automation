#!/usr/bin/env python3
"""Delete the exact prior LinkedIn post only after its replacement is confirmed."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
LEDGER_FILE = ROOT / "published-ledger.json"
TIME_ZONE = ZoneInfo("Asia/Kolkata")
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def git_detail(result):
    return (result.stderr or result.stdout or f"exit code {result.returncode}").strip()


def save_ledger_safely(ledger, old_key, old_post_id, new_key, new_post_id):
    LEDGER_FILE.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for args in (
        ("config", "user.name", "github-actions[bot]"),
        ("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"),
        ("add", "published-ledger.json"),
    ):
        result = git(*args)
        if result.returncode != 0:
            raise RuntimeError(f"Could not stage replacement ledger update: {git_detail(result)}")
    commit = git("commit", "-m", f"Record deleted LinkedIn post replaced by {new_post_id}")
    if commit.returncode != 0:
        raise RuntimeError(f"Could not commit replacement ledger update: {git_detail(commit)}")
    push = git("push", "origin", "HEAD:main")
    if push.returncode == 0:
        return
    detail = git_detail(push).lower()
    if not any(term in detail for term in ("non-fast-forward", "fetch first", "failed to push some refs", "tip of your current branch is behind")):
        raise RuntimeError(
            "The LinkedIn deletion was confirmed, but the ledger update could not be pushed. "
            f"Inspect main before any retry. {git_detail(push)}"
        )
    fetched = git("fetch", "origin", "main")
    if fetched.returncode != 0:
        raise RuntimeError(f"Deletion was confirmed but ledger reconciliation failed: {git_detail(fetched)}")
    remote_result = git("show", "origin/main:published-ledger.json")
    if remote_result.returncode != 0:
        raise RuntimeError(f"Deletion was confirmed but the latest ledger could not be read: {git_detail(remote_result)}")
    try:
        remote = json.loads(remote_result.stdout)
        remote_dates = remote["dates"]
        remote_old = remote_dates[old_key]
        remote_new = remote_dates[new_key]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Remote ledger changed shape; refusing to overwrite it.") from exc
    if not isinstance(remote_old, dict) or remote_old.get("post_id") != old_post_id:
        raise RuntimeError("Remote target ledger record changed; refusing to overwrite it.")
    if not isinstance(remote_new, dict) or remote_new.get("status") != "published" or remote_new.get("post_id") != new_post_id:
        raise RuntimeError("Remote replacement ledger record changed; refusing to overwrite it.")
    if remote_old.get("status") == "replaced" and remote_old.get("replaced_by_post_id") == new_post_id:
        return
    if remote_old.get("status") != "published":
        raise RuntimeError("Remote target ledger status changed; refusing to overwrite it.")
    desired_old = ledger["dates"][old_key]
    remote_old["status"] = "replaced"
    remote_old["replaced_at"] = desired_old["replaced_at"]
    remote_old["replaced_by_post_id"] = new_post_id
    remote_old["note"] = desired_old["note"]
    reset = git("reset", "--hard", "origin/main")
    if reset.returncode != 0:
        raise RuntimeError(f"Could not reset for safe ledger reconciliation: {git_detail(reset)}")
    LEDGER_FILE.write_text(json.dumps(remote, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stage = git("add", "published-ledger.json")
    if stage.returncode != 0:
        raise RuntimeError(f"Could not stage reconciled ledger update: {git_detail(stage)}")
    commit = git("commit", "-m", f"Record deleted LinkedIn post replaced by {new_post_id}")
    if commit.returncode != 0:
        raise RuntimeError(f"Could not commit reconciled ledger update: {git_detail(commit)}")
    retry = git("push", "origin", "HEAD:main")
    if retry.returncode != 0:
        raise RuntimeError(
            "The LinkedIn deletion was confirmed, but the reconciled ledger push failed. "
            f"Inspect main before any retry. {git_detail(retry)}"
        )


def main():
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    request_id = os.getenv("PUBLISH_REQUEST_ID", "").strip()
    old_post_id = os.getenv("REPLACE_POST_ID", "").strip()
    old_key = os.getenv("REPLACE_OLD_LEDGER_KEY", "").strip()
    ratio = os.getenv("PUBLISH_ASPECT_RATIO", "").strip()
    if not token or not request_id.isdigit() or not old_key:
        raise RuntimeError("Missing LinkedIn token or explicit replacement identifiers.")
    if ratio != "9:16":
        raise RuntimeError("Old-post deletion is allowed only for a validated 9:16 replacement.")
    today = datetime.now(TIME_ZONE).date().isoformat()
    new_key = f"{today}-replacement-{request_id}"
    try:
        ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
        dates = ledger["dates"]
        old_record = dates[old_key]
        new_record = dates[new_key]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Could not read both exact records from the publication ledger.") from exc

    if not isinstance(old_record, dict) or old_record.get("status") != "published":
        raise RuntimeError("Target post is not marked published; refusing deletion.")
    if old_record.get("post_id") != old_post_id:
        raise RuntimeError("Old post URN does not match the exact ledger record; refusing deletion.")
    if not isinstance(new_record, dict) or new_record.get("status") != "published":
        raise RuntimeError("Replacement is not confirmed published; old post will remain untouched.")
    new_post_id = str(new_record.get("post_id") or "").strip()
    if not new_post_id or new_post_id == old_post_id:
        raise RuntimeError("Replacement post ID is missing or matches the old post.")
    if new_record.get("video_dimensions") != "1080x1920":
        raise RuntimeError("Replacement ledger entry does not confirm 1080x1920 output.")
    if new_record.get("replaces_post_id") != old_post_id or new_record.get("topic") != old_record.get("topic"):
        raise RuntimeError("Replacement is not tied to this exact old post/topic; refusing deletion.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Linkedin-Version": os.getenv("LINKEDIN_POSTS_API_VERSION", "202609"),
        "X-Restli-Protocol-Version": "2.0.0",
    }
    profile = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if not profile.ok:
        raise RuntimeError(f"Authenticated LinkedIn profile verification failed (HTTP {profile.status_code}).")
    try:
        member_id = profile.json().get("sub")
    except ValueError as exc:
        raise RuntimeError("LinkedIn profile verification returned invalid JSON.") from exc
    if not member_id:
        raise RuntimeError("LinkedIn profile verification did not return the authenticated member ID.")
    owner_urn = f"urn:li:person:{member_id}"

    encoded_old_id = quote(old_post_id, safe="")
    old_url = f"{POSTS_URL}/{encoded_old_id}"
    current = requests.get(old_url, headers=headers, timeout=30)
    if current.status_code in {404, 410}:
        print("The exact old post is already absent from LinkedIn; treating deletion as confirmed.")
    elif current.ok:
        try:
            old_payload = current.json()
        except ValueError as exc:
            raise RuntimeError("LinkedIn returned invalid JSON for the old post; refusing deletion.") from exc
        if old_payload.get("id") and old_payload.get("id") != old_post_id:
            raise RuntimeError("LinkedIn returned a different post ID; refusing deletion.")
        if old_payload.get("author") != owner_urn:
            raise RuntimeError("Authenticated member does not match the old post author; refusing deletion.")
        deletion = requests.delete(
            old_url,
            headers={**headers, "X-RestLi-Method": "DELETE"},
            timeout=30,
        )
        if deletion.status_code != 204:
            detail = deletion.text[:500].replace(token, "[REDACTED]")
            raise RuntimeError(f"LinkedIn did not confirm deletion (HTTP {deletion.status_code}): {detail}")
        print(f"LinkedIn confirmed deletion of {old_post_id} (HTTP 204).")
    else:
        raise RuntimeError(
            f"Could not verify ownership of the old post (HTTP {current.status_code}); no deletion was attempted."
        )

    old_record["status"] = "replaced"
    old_record["replaced_at"] = datetime.now(TIME_ZONE).isoformat(timespec="seconds")
    old_record["replaced_by_post_id"] = new_post_id
    old_record["note"] = "Deleted via authenticated LinkedIn Posts API after the replacement was confirmed published."
    save_ledger_safely(ledger, old_key, old_post_id, new_key, new_post_id)
    print("SUCCESS: Old post deletion confirmed and the ledger now records it as replaced.")
    print(f"Replacement post ID: {new_post_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
