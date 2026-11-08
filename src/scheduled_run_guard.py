"""Guard scheduled LinkedIn runs against wrong-day and overnight publication.

GitHub can deliver schedule events late. We accept delayed runs on the intended
India-local publishing weekday, but never let a delayed event move a post to a
different weekday or cross midnight. Duplicate and uncertainty checks remain
in the publication ledger.
"""

from datetime import datetime

# Keep these expressions in sync with .github/workflows/daily-linkedin.yml.
SCHEDULE_WEEKDAYS = {
    "30 3-8 * * 2": (1, "Tuesday"),
    "30 3-8 * * 5": (4, "Friday"),
    "30 16 * * 2": (1, "Tuesday"),
    "30 16 * * 5": (4, "Friday"),
}

# The 22:00 IST final recovery trigger gets a same-day processing window.
# Refuse new scheduled publications from 23:00 IST onward so a generation or
# upload cannot intentionally start near the date boundary.
LATEST_START_HOUR = 23


def scheduled_run_eligibility(
    now: datetime, schedule_expression: str
) -> tuple[bool, str, bool]:
    """Return (eligible, explanation, is_late_delivery) for a scheduled run."""
    expression = str(schedule_expression or "").strip()
    schedule = SCHEDULE_WEEKDAYS.get(expression)
    if schedule is None:
        return (
            False,
            f"unknown or missing GitHub schedule expression {expression!r}",
            False,
        )

    expected_weekday, expected_name = schedule
    if now.weekday() != expected_weekday:
        actual_name = now.strftime("%A")
        return (
            False,
            f"{expected_name} schedule was delivered on {actual_name}; refusing to move it to another day",
            False,
        )

    if now.hour >= LATEST_START_HOUR:
        return (
            False,
            f"scheduled run started at {now.strftime('%H:%M')} IST, at or after the 23:00 same-day cutoff",
            True,
        )

    is_late = now.hour >= 15
    if is_late:
        return (
            True,
            f"{expected_name} schedule arrived late at {now.strftime('%H:%M')} IST; same-day recovery is still allowed",
            True,
        )

    return (True, f"{expected_name} scheduled run is within its normal publishing day", False)
