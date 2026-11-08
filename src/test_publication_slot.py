#!/usr/bin/env python3
"""Regression tests for scheduled publication preflight duplicate safeguards."""

import contextlib
import io
import json
import os
import tempfile
from datetime import datetime as RealDateTime
from pathlib import Path

import check_publication_slot as slot
from scheduled_run_guard import scheduled_run_eligibility


class FixedDateTime:
    value = RealDateTime(2026, 10, 27, 9, 12)

    @classmethod
    def now(cls, tz=None):
        return cls.value.replace(tzinfo=tz)


def run_preflight(records, now=None, intent="scheduled", schedule_expression="30 3-8 * * 2"):
    original_ledger = slot.LEDGER_FILE
    original_datetime = slot.datetime
    original_write_output = slot.write_output
    original_fixed_value = FixedDateTime.value
    original_intent = os.environ.get("PUBLISH_INTENT")
    original_schedule_expression = os.environ.get("PUBLISH_SCHEDULE_EXPRESSION")
    outputs = {}
    stdout = io.StringIO()
    error = None
    result = None

    try:
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "published-ledger.json"
            ledger_path.write_text(
                json.dumps({"timezone": "Asia/Kolkata", "dates": records}),
                encoding="utf-8",
            )
            slot.LEDGER_FILE = ledger_path
            slot.datetime = FixedDateTime
            FixedDateTime.value = now or RealDateTime(2026, 10, 27, 9, 12)
            slot.write_output = lambda name, value: outputs.__setitem__(name, value)
            os.environ["PUBLISH_INTENT"] = intent
            os.environ["PUBLISH_SCHEDULE_EXPRESSION"] = schedule_expression
            with contextlib.redirect_stdout(stdout):
                try:
                    result = slot.main()
                except RuntimeError as exc:
                    error = str(exc)
    finally:
        slot.LEDGER_FILE = original_ledger
        slot.datetime = original_datetime
        slot.write_output = original_write_output
        FixedDateTime.value = original_fixed_value
        if original_intent is None:
            os.environ.pop("PUBLISH_INTENT", None)
        else:
            os.environ["PUBLISH_INTENT"] = original_intent
        if original_schedule_expression is None:
            os.environ.pop("PUBLISH_SCHEDULE_EXPRESSION", None)
        else:
            os.environ["PUBLISH_SCHEDULE_EXPRESSION"] = original_schedule_expression

    return result, stdout.getvalue(), outputs, error


def main():
    _, output, outputs, error = run_preflight({
        "2026-10-26-request-70": {"status": "replaced"},
        "2026-10-27-replacement-71": {"status": "published", "post_id": "urn:confirmed"},
    })
    if error or outputs.get("should_run") != "false" or "SKIP:" not in output:
        raise SystemExit("A confirmed same-day replacement must block a second scheduled post.")

    _, _, outputs, error = run_preflight({
        "2026-10-27-replacement-72": {"status": "needs_review"},
    })
    if not error or "needs_review" not in error or outputs.get("should_run") == "true":
        raise SystemExit("An uncertain same-day replacement must fail closed.")

    _, _, outputs, error = run_preflight({})
    if error or outputs.get("should_run") != "true":
        raise SystemExit("An empty daily ledger must leave the scheduled slot available.")

    _, _, outputs, error = run_preflight({
        "2026-10-27-request-73": {"status": "replaced"},
    })
    if not error or "no confirmed published replacement" not in error:
        raise SystemExit("A replaced entry without a confirmed replacement must fail closed.")

    _, output, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 28, 10, 0)
    )
    if error or outputs.get("should_run") != "false" or "outside the Tuesday/Friday" not in output:
        raise SystemExit("A queued scheduled run on a non-publishing weekday must skip.")

    # A delayed Tuesday event at 15:00 and 16:40 IST must still be able
    # to publish on Tuesday rather than being discarded by an hour cutoff.
    for late_time in (RealDateTime(2026, 10, 27, 15, 0), RealDateTime(2026, 10, 27, 16, 40)):
        _, output, outputs, error = run_preflight({}, now=late_time)
        if error or outputs.get("should_run") != "true" or "LATE DELIVERY" not in output:
            raise SystemExit("A delayed Tuesday event must remain eligible on Tuesday.")

    _, _, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 30, 14, 59),
        schedule_expression="30 3-8 * * 5"
    )
    if error or outputs.get("should_run") != "true":
        raise SystemExit("A Friday recovery run must remain eligible on Friday.")

    _, output, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 30, 22, 30),
        schedule_expression="30 16 * * 5"
    )
    if error or outputs.get("should_run") != "true" or "LATE DELIVERY" not in output:
        raise SystemExit("The final 22:00 IST Friday recovery event must remain eligible that evening.")

    # An old Friday event delivered on Tuesday must not be mistaken for the
    # current Tuesday schedule and must never shift a publication to a new day.
    _, output, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 11, 3, 16, 40),
        schedule_expression="30 3-8 * * 5"
    )
    if error or outputs.get("should_run") != "false" or "Friday schedule was delivered on Tuesday" not in output:
        raise SystemExit("A delayed Friday schedule arriving on Tuesday must be refused.")

    _, output, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 27, 23, 0)
    )
    if error or outputs.get("should_run") != "false" or "23:00 same-day cutoff" not in output:
        raise SystemExit("A run arriving at the 23:00 IST safety cutoff must be refused.")

    _, _, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 28, 10, 0), intent="preview"
    )
    if error or outputs.get("should_run") != "true":
        raise SystemExit("Manual preview mode must remain available outside scheduled windows.")

    # Verify both normal and final fallback cron expressions are recognized.
    for expression, timestamp in (
        ("30 3-8 * * 2", RealDateTime(2026, 10, 27, 9, 0)),
        ("30 3-8 * * 5", RealDateTime(2026, 10, 30, 9, 0)),
        ("30 16 * * 2", RealDateTime(2026, 10, 27, 22, 0)),
        ("30 16 * * 5", RealDateTime(2026, 10, 30, 22, 0)),
    ):
        eligible, _, _ = scheduled_run_eligibility(
            timestamp.replace(tzinfo=slot.TIME_ZONE), expression
        )
        if not eligible:
            raise SystemExit(f"Expected schedule expression to be eligible: {expression}")

    print("Publication-slot safeguards passed: duplicates blocked, uncertain state fails closed, late same-day delivery accepted, wrong-day/overnight delivery refused, and final recovery cron recognized.")


if __name__ == "__main__":
    main()
