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
    if intent not in {"scheduled", "request", "correction", "extra", "extra_override", "longform", "longform_recovery", "reformat", "plan_extra", "replacement"}:
        raise RuntimeError(f"Unsupported PUBLISH_INTENT: {intent!r}")

    request_id = os.getenv("PUBLISH_REQUEST_ID", "").strip()
    if intent in {"request", "correction", "extra", "extra_override", "longform", "reformat", "plan_extra", "replacement"} and not request_id.isdigit():
        raise RuntimeError("A numeric PUBLISH_REQUEST_ID is required for one-off publication requests.")

    today = datetime.now(TIME_ZONE).date().isoformat()
    dates = load_dates()

    if intent == "longform":
        # This narrowly scoped, owner-requested long video is allowed only
        # for the next verified plan topic (Day 15), once per India-local date.
        if os.getenv("PUBLISH_TOPIC_DAY", "").strip() != "15":
            raise RuntimeError("Long-form publishing is restricted to the next planned topic, Day 15.")
        if os.getenv("PUBLISH_LONGFORM", "").strip().lower() not in {"1", "true", "yes"}:
            raise RuntimeError("Long-form publication requires PUBLISH_LONGFORM=true.")
        if os.getenv("PUBLISH_VIDEO_DURATION_SECONDS", "").strip() != "90":
            raise RuntimeError("Long-form publication requires a validated 90-second render.")
        longform_key = f"{today}-longform-{request_id}"
        day_prefix = f"{today}-"
        day_records = [
            (key, record) for key, record in dates.items()
            if key == today or key.startswith(day_prefix)
        ]
        baseline_published = any(
            isinstance(record, dict) and record.get("status") == "published"
            for _, record in day_records
        )
        if not baseline_published:
            raise RuntimeError("Long-form publication requires an earlier confirmed post today.")
        uncertain = [
            key for key, record in day_records
            if isinstance(record, dict) and record.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before publishing another video."
            )
        prior_longforms = [
            key for key, record in day_records
            if key.startswith(f"{today}-longform-")
            and isinstance(record, dict)
            and record.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_longforms:
            raise RuntimeError("A long-form LinkedIn video was already attempted today.")
        if longform_key in dates:
            raise RuntimeError(f"Long-form ledger entry {longform_key} already exists; refusing to retry.")
        print(f"READY: Explicit long-form Day 15 request is clear ({today}).")
        write_output("should_run", "true")
        return 0

    if intent == "extra_override":
        # Explicit user-approved second post, restricted to the next planned
        # topic. The normal one-post and one-extra-post safeguards stay intact.
        if os.getenv("PUBLISH_TOPIC_DAY", "").strip() != "14":
            raise RuntimeError("Same-day override is restricted to the next planned topic, Day 14.")
        override_key = f"{today}-extra-override-{request_id}"
        day_prefix = f"{today}-"
        day_records = [
            (key, record) for key, record in dates.items()
            if key == today or key.startswith(day_prefix)
        ]
        baseline_published = any(
            isinstance(record, dict) and record.get("status") == "published"
            for _, record in day_records
        )
        if not baseline_published:
            raise RuntimeError("A same-day override requires an earlier confirmed publication today.")
        uncertain = [
            key for key, record in day_records
            if isinstance(record, dict) and record.get("status") in {"publishing", "needs_review"}
        ]
        if uncertain:
            raise RuntimeError(
                "Today's ledger has an in-progress or uncertain publication "
                f"({', '.join(uncertain)}). Inspect LinkedIn before publishing another post."
            )
        prior_overrides = [
            key for key, record in day_records
            if key.startswith(f"{today}-extra-override-")
            and isinstance(record, dict)
            and record.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_overrides:
            raise RuntimeError("A same-day override post was already attempted today.")
        if override_key in dates:
            raise RuntimeError(f"Override ledger entry {override_key} already exists; refusing to retry.")
        print(f"READY: Explicit same-day override for planned Day 14 is clear ({today}).")
        write_output("should_run", "true")
        return 0

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

    if intent == "replacement":
        replacement_key = f"{today}-replacement-{request_id}"
        old_post_id = os.getenv("PUBLISH_REPLACEMENT_OLD_POST_ID", "").strip()
        old_ledger_key = os.getenv("PUBLISH_REPLACEMENT_OLD_LEDGER_KEY", "").strip()
        expected_topic = os.getenv("PUBLISH_EXPECTED_TOPIC", "").strip()
        requested_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
        old_record = dates.get(old_ledger_key)
        if not old_post_id or not old_ledger_key or not expected_topic or not requested_day.isdigit():
            raise RuntimeError("Replacement preflight is missing the exact target post or verified topic.")
        if not isinstance(old_record, dict) or old_record.get("status") != "published":
            raise RuntimeError("Replacement target is not a confirmed published post.")
        if old_record.get("post_id") != old_post_id or old_record.get("topic") != expected_topic:
            raise RuntimeError("Replacement target ID/topic does not match the confirmed ledger record.")
        def record_time(item):
            key, record = item
            stamp_text = record.get("published_at") or record.get("started_at") or record.get("recorded_at") or str(key)[:10]
            try:
                stamp = datetime.fromisoformat(str(stamp_text).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                stamp = datetime.fromisoformat(str(key)[:10]).replace(tzinfo=TIME_ZONE)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=TIME_ZONE)
            return (stamp.timestamp(), str(key))
        published = [
            (key, value) for key, value in dates.items()
            if isinstance(value, dict) and value.get("status") == "published"
        ]
        if not published or max(published, key=record_time)[0] != old_ledger_key:
            raise RuntimeError("Replacement target is no longer the latest confirmed post.")
        day_records = [
            (key, value) for key, value in dates.items()
            if key == today or key.startswith(f"{today}-")
        ]
        unsafe_today = [
            key for key, value in day_records
            if isinstance(value, dict) and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if unsafe_today:
            raise RuntimeError(
                "Today's ledger already contains a published or uncertain post "
                f"({', '.join(unsafe_today)}); refusing a second publication."
            )
        if replacement_key in dates:
            raise RuntimeError(f"Replacement ledger key {replacement_key} already exists; refusing to retry.")
        prior_replacements = [
            key for key, value in dates.items()
            if isinstance(value, dict)
            and value.get("replaces_post_id") == old_post_id
            and value.get("status") in {"published", "publishing", "needs_review"}
        ]
        if prior_replacements:
            raise RuntimeError("This original post already has a replacement attempt recorded.")
        print(f"READY: exact latest post {old_post_id} may be replaced once today.")
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

    # The scheduled slot must account for every ledger key created today, not
    # only the base date and request keys. In particular, a confirmed replacement
    # or explicitly requested extra post must suppress a second scheduled post.
    day_prefix = f"{today}-"
    day_records = []
    for key, record in dates.items():
        if key != today and not key.startswith(day_prefix):
            continue
        if not isinstance(record, dict):
            raise RuntimeError(f"Malformed ledger entry for {key}; refusing to continue.")
        day_records.append((key, record))

    for key, record in day_records:
        status = record.get("status")
        if status in {"publishing", "needs_review"}:
            raise RuntimeError(
                f"Ledger entry {key} is '{status}'. Inspect LinkedIn and the ledger manually; "
                "no content or video was generated."
            )
        if status not in {"published", "replaced"}:
            raise RuntimeError(
                f"Unexpected ledger status {status!r} for {key}; refusing to spend API usage or risk a duplicate."
            )

    published_today = [
        key for key, record in day_records if record.get("status") == "published"
    ]
    if published_today:
        published_keys = ", ".join(published_today)
        print(
            f"SKIP: Today's India-local publishing slot ({today}) is already recorded as published "
            f"({published_keys}). Gemini and FFmpeg will not run."
        )
        write_output("should_run", "false")
        return 0

    if day_records:
        # A replaced record without its confirmed replacement is not enough
        # evidence that today's slot is clear. Fail closed for manual review.
        replaced_keys = ", ".join(
            key for key, record in day_records if record.get("status") == "replaced"
        )
        raise RuntimeError(
            f"Today's ledger has replaced entry/entries ({replaced_keys}) but no confirmed "
            "published replacement. Inspect the ledger and LinkedIn before continuing."
        )

    print(f"READY: No publication is recorded for {today} in Asia/Kolkata; generation may proceed.")
    write_output("should_run", "true")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
