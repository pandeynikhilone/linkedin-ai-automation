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


class FixedDateTime:
    value = RealDateTime(2026, 10, 27, 9, 12)

    @classmethod
    def now(cls, tz=None):
        return cls.value.replace(tzinfo=tz)


def run_preflight(records, now=None, intent="scheduled"):
    original_ledger = slot.LEDGER_FILE
    original_datetime = slot.datetime
    original_write_output = slot.write_output
    original_fixed_value = FixedDateTime.value
    original_intent = os.environ.get("PUBLISH_INTENT")
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

    _, output, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 27, 15, 0)
    )
    if error or outputs.get("should_run") != "false" or "outside the Tuesday/Friday" not in output:
        raise SystemExit("A queued scheduled run after the 14:00 recovery window must skip.")

    _, _, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 30, 14, 59)
    )
    if error or outputs.get("should_run") != "true":
        raise SystemExit("A delayed Friday recovery run must remain eligible through 14:59 IST.")

    _, _, outputs, error = run_preflight(
        {}, now=RealDateTime(2026, 10, 28, 10, 0), intent="preview"
    )
    if error or outputs.get("should_run") != "true":
        raise SystemExit("Manual preview mode must remain available outside scheduled windows.")

    print("Publication-slot safeguards passed: duplicates blocked, uncertain state fails closed, empty slots remain available, and queued scheduled runs outside Tuesday/Friday 09:00-14:59 IST skip safely.")


if __name__ == "__main__":
    main()
