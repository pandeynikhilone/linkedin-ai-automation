#!/usr/bin/env python3
"""Build a public-safe dashboard snapshot from the private plan and publication ledger.

Only planned topic titles, dates, coarse statuses, and confirmed LinkedIn post URLs
are emitted. Supporting source facts, post text, tokens, and ledger internals stay private.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PLAN_FILE = ROOT / "content-plan.json"
LEDGER_FILE = ROOT / "published-ledger.json"
OUTPUT_FILE = ROOT / "dashboard" / "data.json"
TZ = ZoneInfo("Asia/Kolkata")
REQUEST_TITLE = re.compile(r"^Publish Day (\d{1,2}) LinkedIn post now$")
REQUEST_MARKER = re.compile(r"^PUBLISH_PLAN_DAY=(\d{1,2})$", re.MULTILINE)
VALID_LEDGER_STATUSES = {"published", "publishing", "needs_review"}


def parse_timestamp(value: object, fallback_key: str = "") -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None
    except ValueError:
        parsed = None
    if parsed is None and fallback_key:
        try:
            parsed = datetime.fromisoformat(fallback_key[:10])
        except ValueError:
            parsed = None
    if parsed is None:
        return datetime.min.replace(tzinfo=TZ)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def load_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def read_issues() -> list[dict]:
    path = os.getenv("DASHBOARD_ISSUES_FILE", "").strip()
    if not path:
        return []
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def read_request(issue: dict, topic_count: int) -> dict | None:
    title = str(issue.get("title", ""))
    match = REQUEST_TITLE.fullmatch(title)
    body = str(issue.get("body") or "")
    marker = REQUEST_MARKER.search(body)
    if not match or not marker:
        return None
    try:
        title_day = int(match.group(1))
        marker_day = int(marker.group(1))
    except ValueError:
        return None
    if title_day != marker_day or not 1 <= title_day <= topic_count:
        return None
    created_at = parse_timestamp(issue.get("created_at"))
    state = str(issue.get("state", "")).lower()
    body_status = re.search(r"^REQUEST_STATUS:\s*(OPEN|PUBLISHED|FAILED|SKIPPED)$", body, re.MULTILINE | re.IGNORECASE)
    request_status = body_status.group(1).lower() if body_status else ("queued" if state == "open" else "closed")
    return {
        "day": title_day,
        "number": issue.get("number"),
        "state": state,
        "status": request_status,
        "createdAt": created_at.isoformat(timespec="seconds"),
        "createdDate": created_at.date().isoformat(),
        "updatedAt": parse_timestamp(issue.get("updated_at") or issue.get("closed_at") or issue.get("created_at")).isoformat(timespec="seconds"),
        "url": str(issue.get("html_url") or ""),
    }


def main() -> None:
    plan = load_json(PLAN_FILE, {})
    ledger = load_json(LEDGER_FILE, {"timezone": "Asia/Kolkata", "dates": {}})
    if not isinstance(plan, dict) or not isinstance(plan.get("topics"), list):
        raise SystemExit("content-plan.json has no valid topics list.")
    if not isinstance(ledger, dict) or not isinstance(ledger.get("dates"), dict):
        raise SystemExit("published-ledger.json has an unexpected structure.")

    plan_topics = plan["topics"]
    if not plan_topics or any(not isinstance(item, dict) or not item.get("topic") for item in plan_topics):
        raise SystemExit("Every plan topic must have a title.")
    topic_count = len(plan_topics)
    day_by_topic = {str(item["topic"]): int(item.get("day", idx + 1)) for idx, item in enumerate(plan_topics)}
    now = datetime.now(TZ)
    today = now.date()
    raw_records = ledger["dates"]
    ledger_by_day: dict[int, list[dict]] = {int(item.get("day", idx + 1)): [] for idx, item in enumerate(plan_topics)}
    all_plan_records: list[dict] = []
    today_records: list[tuple[str, dict]] = []

    for key, raw in raw_records.items():
        if not isinstance(raw, dict):
            continue
        topic = str(raw.get("topic") or "")
        day = day_by_topic.get(topic)
        stamp = parse_timestamp(raw.get("published_at") or raw.get("started_at") or raw.get("recorded_at"), str(key))
        item = {"key": str(key), "topic": topic, "day": day, "status": str(raw.get("status", "")).lower(),
                "stamp": stamp, "publishedAt": parse_timestamp(raw.get("published_at"), str(key)).isoformat(timespec="seconds") if raw.get("published_at") else None,
                "postId": str(raw.get("post_id") or "")}
        if day is not None:
            ledger_by_day[day].append(item)
            all_plan_records.append(item)
        if str(key) == today.isoformat() or str(key).startswith(today.isoformat() + "-"):
            today_records.append((str(key), raw))

    confirmed = [item for item in all_plan_records if item["status"] == "published"]
    latest_confirmed = max(confirmed, key=lambda item: item["stamp"], default=None)
    issues = [item for item in (read_request(issue, topic_count) for issue in read_issues()) if item]
    latest_issue_by_day: dict[int, dict] = {}
    for issue in issues:
        current = latest_issue_by_day.get(issue["day"])
        issue_stamp = parse_timestamp(issue.get("createdAt"))
        if current is None or issue_stamp > parse_timestamp(current.get("createdAt")):
            latest_issue_by_day[issue["day"]] = issue

    open_requests_today = [
        issue for issue in issues
        if issue["state"] == "open" and issue["createdDate"] == today.isoformat()
    ]
    active_today = [
        (key, raw) for key, raw in today_records
        if isinstance(raw, dict) and str(raw.get("status", "")).lower() in VALID_LEDGER_STATUSES
    ]
    slot_available = not active_today and not open_requests_today
    if open_requests_today:
        slot_message = "A publishing request is already open for today. Resolve it before starting another request."
    elif active_today:
        names = ", ".join(key for key, _ in active_today[:3])
        slot_message = "Today’s Asia/Kolkata publishing slot is already used or reserved (" + names + "). Duplicate protection has disabled all Publish buttons."
    else:
        slot_message = "No publication or open request is recorded for today. One owner-triggered post can be requested."

    actual_dates: dict[int, date] = {}
    for day in range(1, topic_count + 1):
        published = [item for item in ledger_by_day.get(day, []) if item["status"] == "published"]
        latest = max(published, key=lambda item: item["stamp"], default=None)
        if latest is not None:
            actual_dates[day] = latest["stamp"].date()

    if latest_confirmed is not None:
        latest_day = int(latest_confirmed["day"])
        next_day_expected = (latest_day % topic_count) + 1
        sequence_start = latest_confirmed["stamp"].date()
    else:
        latest_day = 0
        next_day_expected = int(plan_topics[0].get("day", 1))
        sequence_start = date.fromisoformat(str(plan.get("startDate", today.isoformat())))

    topics_out = []
    for idx, topic_item in enumerate(plan_topics, start=1):
        day = int(topic_item.get("day", idx))
        topic = str(topic_item["topic"])
        records = sorted(ledger_by_day.get(day, []), key=lambda item: item["stamp"])
        latest_record = records[-1] if records else None
        issue = latest_issue_by_day.get(day)
        open_issue = issue if issue and issue["state"] == "open" else None
        latest_record_stamp = latest_record["stamp"] if latest_record else datetime.min.replace(tzinfo=TZ)
        issue_stamp = parse_timestamp(issue.get("createdAt")) if issue else datetime.min.replace(tzinfo=TZ)
        unresolved_record = latest_record and latest_record["status"] in {"publishing", "needs_review"}
        has_published_record = any(item["status"] == "published" for item in records)
        post_record = max((item for item in records if item["status"] == "published"), key=lambda item: item["stamp"], default=None)

        status = "planned"
        if unresolved_record:
            status = "publishing" if latest_record["status"] == "publishing" else "needs_review"
        elif open_issue and issue_stamp >= latest_record_stamp:
            status = "queued"
        elif latest_record and latest_record["status"] == "published":
            status = "published"
        elif issue and issue["state"] == "closed":
            if issue["status"] == "failed":
                status = "failed"
            elif issue["status"] == "skipped":
                status = "skipped"
            elif issue["status"] == "published" and not has_published_record:
                status = "needs_review"
            elif issue["status"] == "open":
                status = "queued"
            elif has_published_record:
                status = "published"

        if day in actual_dates:
            planned_date = actual_dates[day]
        elif latest_confirmed is not None:
            distance = (day - latest_day) % topic_count
            if distance == 0:
                distance = topic_count
            planned_date = sequence_start + timedelta(days=distance)
        else:
            planned_date = date.fromisoformat(str(plan.get("startDate", today.isoformat()))) + timedelta(days=day - 1)

        post_id = post_record["postId"] if post_record else ""
        post_url = ""
        if post_id.startswith("urn:li:ugcPost:"):
            post_url = "https://www.linkedin.com/feed/update/" + post_id + "/"

        row_unresolved = status in {"publishing", "needs_review"}
        can_publish = bool(slot_available and status == "planned" and day == next_day_expected and not row_unresolved and not open_issue)
        if status == "queued":
            can_publish = False
        topics_out.append({
            "day": day,
            "topic": topic,
            "plannedDate": planned_date.isoformat(),
            "status": status,
            "statusLabel": status.replace("_", " ").title(),
            "publishedAt": post_record["publishedAt"] if post_record else None,
            "postUrl": post_url,
            "canPublish": can_publish,
            "requestOpen": open_issue is not None,
            "slotAvailable": slot_available,
        })

    next_topic = None
    if latest_confirmed is not None:
        next_day = (int(latest_confirmed["day"]) % topic_count) + 1
        next_item = next((item for item in plan_topics if int(item.get("day", 0)) == next_day), plan_topics[next_day - 1])
        next_topic = {"day": next_day, "topic": str(next_item["topic"]),
                      "plannedDate": (latest_confirmed["stamp"].date() + timedelta(days=1)).isoformat()}
    else:
        next_item = plan_topics[0]
        next_topic = {"day": int(next_item.get("day", 1)), "topic": str(next_item["topic"]),
                      "plannedDate": str(plan.get("startDate", today.isoformat()))}

    queued_count = sum(1 for issue in issues if issue["state"] == "open")
    status_counts = {name: sum(1 for row in topics_out if row["status"] == name)
                     for name in ("published", "planned", "queued", "publishing", "needs_review", "failed", "skipped")}
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": str(plan.get("title", "LinkedIn Content Plan")),
        "timezone": "Asia/Kolkata",
        "generatedAt": now.isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "slotAvailable": slot_available,
        "slotMessage": slot_message,
        "nextTopic": next_topic,
        "summary": {
            "total": topic_count,
            "published": status_counts["published"],
            "queued": queued_count,
            "needsAttention": status_counts["needs_review"] + status_counts["failed"],
        },
        "topics": topics_out,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built dashboard data for {topic_count} topics; today’s slot available={slot_available}; open requests={queued_count}.")


if __name__ == "__main__":
    main()
