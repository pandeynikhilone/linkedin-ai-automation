#!/usr/bin/env python3
"""Check today's LinkedIn publishing slot before any paid API or video work."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LEDGER_FILE = ROOT / "published-ledger.json"
TIME_ZONE = ZoneInfo("Asia/Kolkata")


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def load_dates() -> dict:
    if not LEDGER_FILE.exists():
        return {}
    try:
        ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Cannot safely read published-ledger.json; refusing to generate content.") from exc
    if not isinstance(ledger, dict) or not isinstance(ledger.get("dates"), dict):
        raise RuntimeError("Publication ledger has an unexpected structure; refusing to continue.")
    return ledger["dates"]


def main() -> int:
    intent = os.getenv("PUBLISH_INTENT", "scheduled").strip().lower()
    if intent in {"preview", "workflow_dispatch"}:
        print("PREVIEW: Manual workflow run is preview-only, so the publication ledger will not block it.")
        write_output("should_run", "true")
        return 0
    if intent not in {"scheduled", "request", "correction", "extra", "reformat", "plan_extra"}:
        raise RuntimeError(f"Unsupported PUBLISH_INTENT: {intent!r}")

    request_id = os.getenv("PUBLISH_REQUEST_ID", "").strip()
    if intent in {"request", "correction", "extra", "reformat", "plan_extra"} and not request_id.isdigit():
        raise RuntimeError("A numeric PUBLISH_REQUEST_ID is required for one-off publication requests.")

    today = datetime.now(TIME_ZONE).date().isoformat()
    dates = load_dates()

    if intent == "extra":
        extra_key = f"{today}-extra-{request_id}"
        day_prefix = f"{today}-"
        day_records = [
            (key, record) for key, record in dates.items()
            if key == today or key.startswith(day_prefix)
        ]
        baseline_published = any(
            record.get("status") == "published" and "-extra-" not in key
            for key, record in day_records if isinstance(record, dict)
        )
        if not baseline_published:
            raise RuntimeError("An extra post requires at least one confirmed publication today.")
        uncertain = [
            key for key, record in day_records
            if isinstance(record, dict) and record.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger contains an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before publishing an extra post."
            )
        if any(
            key.startswith(f"{today}-extra-")
            and key != extra_key
            and isinstance(record, dict)
            and record.get("status") in {"published", "publishing", "needs_review"}
            for key, record in day_records
        ):
            raise RuntimeError("An extra LinkedIn post was already attempted today.")
        if extra_key in dates:
            raise RuntimeError(f"Extra-post ledger entry {extra_key} already exists; refusing to retry.")
        print(f"READY: One explicitly requested extra post is available for today ({today}).")
        write_output("should_run", "true")
        return 0

    if intent == "correction":
        correction_key = f"{today}-correction-{request_id}"
        day_prefix = f"{today}-"
        day_records = [
            (key, record) for key, record in dates.items()
            if key == today or key.startswith(day_prefix)
        ]
        baseline_published = any(
            record.get("status") == "published" and "-correction-" not in key
            for key, record in day_records if isinstance(record, dict)
        )
        if not baseline_published:
            raise RuntimeError("A correction post is allowed only when today's original post is confirmed published.")
        uncertain = [
            key for key, record in day_records
            if isinstance(record, dict) and record.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger contains an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before trying a correction."
            )
        if any(
            key.startswith(f"{today}-correction-")
            and isinstance(record, dict)
            and record.get("status") in {"published", "publishing", "needs_review"}
            for key, record in day_records
        ):
            raise RuntimeError("A correction video was already attempted today. Refusing a second correction post.")
        if correction_key in dates:
            raise RuntimeError(f"Correction ledger entry {correction_key} already exists; refusing to retry.")
        print(f"READY: Today's original post is confirmed. One corrected replacement post may be published ({today}).")
        write_output("should_run", "true")
        return 0

    if intent == "reformat":
        reformat_key = f"{today}-reformat-{request_id}"
        expected_topic = "Debugging TypeScript and chart rendering issues"
        day_prefix = f"{today}-"
        day_records = [
            (key, record) for key, record in dates.items()
            if key == today or key.startswith(day_prefix)
        ]
        baseline_published = any(
            isinstance(record, dict)
            and record.get("status") == "published"
            and record.get("topic") == expected_topic
            and "-reformat-" not in key
            for key, record in day_records
        )
        if not baseline_published:
            raise RuntimeError("A Day 5 reformat requires today's confirmed original Day 5 publication.")
        uncertain = [
            key for key, record in day_records
            if isinstance(record, dict) and record.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger contains an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before reformatting."
            )
        if any(
            key.startswith(f"{today}-reformat-")
            and isinstance(record, dict)
            and record.get("status") in {"published", "publishing", "needs_review"}
            for key, record in day_records
        ):
            raise RuntimeError("A reformatted LinkedIn post was already attempted today.")
        if reformat_key in dates:
            raise RuntimeError(f"Reformat ledger entry {reformat_key} already exists; refusing to retry.")
        print(f"READY: Today's original Day 5 post is confirmed; one formatted replacement may be published ({today}).")
        write_output("should_run", "true")
        return 0

    if intent == "plan_extra":
        plan_extra_key = f"{today}-plan-extra-{request_id}"
        expected_topic = "Making chart components easier to extend"
        requested_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
        if requested_day != "6":
            raise RuntimeError("The dedicated planned-extra intent is currently restricted to Day 6.")
        day_records = [
            (key, record) for key, record in dates.items()
            if key == today or key.startswith(f"{today}-")
        ]
        baseline_published = any(
            isinstance(record, dict) and record.get("status") == "published"
            and "-plan-extra-" not in key and record.get("topic") != expected_topic
            for key, record in day_records
        )
        if not baseline_published:
            raise RuntimeError("A Day 6 extra post requires a confirmed publication earlier today.")
        uncertain = [
            key for key, record in day_records
            if isinstance(record, dict) and record.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger contains an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before continuing."
            )
        if any(
            isinstance(record, dict) and record.get("topic") == expected_topic
            and record.get("status") in {"published", "publishing", "needs_review"}
            and (key.startswith(f"{today}-") or key == today)
            for key, record in dates.items()
        ):
            raise RuntimeError("Day 6 already has a published or uncertain ledger record today.")
        if plan_extra_key in dates:
            raise RuntimeError(f"Planned-extra ledger entry {plan_extra_key} already exists.")
        print(f"READY: The Day 6 topic is unused today ({today}); the scheduled 04:00 IST time is unchanged.")
        write_output("should_run", "true")
        return 0

    relevant = []
    daily_record = dates.get(today)
    if daily_record is not None:
        if not isinstance(daily_record, dict):
            raise RuntimeError(f"Malformed ledger entry for {today}; refusing to continue.")
        relevant.append((today, daily_record))

    request_prefix = f"{today}-request-"
    for key, record in dates.items():
        if key.startswith(request_prefix):
            if not isinstance(record, dict):
                raise RuntimeError(f"Malformed ledger entry for {key}; refusing to continue.")
            relevant.append((key, record))

    for key, record in relevant:
        status = record.get("status")
        if status in {"publishing", "needs_review"}:
            raise RuntimeError(
                f"Ledger entry {key} is '{status}'. Inspect LinkedIn and the ledger manually; "
                "no content or video was generated."
            )
        if status != "published":
            raise RuntimeError(
                f"Unexpected ledger status {status!r} for {key}; refusing to spend API usage or risk a duplicate."
            )

    if relevant:
        published_keys = ", ".join(key for key, _ in relevant)
        print(
            f"SKIP: Today's India-local publishing slot ({today}) is already recorded as published "
            f"({published_keys}). Gemini and FFmpeg will not run."
        )
        write_output("should_run", "false")
        return 0

    print(f"READY: No publication is recorded for {today} in Asia/Kolkata; generation may proceed.")
    write_output("should_run", "true")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
