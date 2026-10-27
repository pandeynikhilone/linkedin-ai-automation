#!/usr/bin/env python3
"""Regression tests for scheduled publication preflight duplicate safeguards."""

import contextlib
import io
import json
import os
import tempfile
from datetime import datetime as RealDateTime
from pathlib import Path

from src import check_publication_slot as slot


class FixedDateTime:
    @classmethod
    def now(cls, tz=None):
        return RealDateTime(2026, 10, 27, 8, 12, tzinfo=tz)


def run_preflight(records):
    original_ledger = slot.LEDGER_FILE
    original_datetime = slot.datetime
    original_write_output = slot.write_output
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
            slot.write_output = lambda name, value: outputs.__setitem__(name, value)
            os.environ["PUBLISH_INTENT"] = "scheduled"
            with contextlib.redirect_stdout(stdout):
                try:
                    result = slot.main()
                except RuntimeError as exc:
                    error = str(exc)
    finally:
        slot.LEDGER_FILE = original_ledger
        slot.datetime = original_datetime
        slot.write_output = original_write_output
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

    print("Publication-slot safeguards passed: replacement blocks duplicates, uncertain state fails closed, and an empty slot remains available.")


if __name__ == "__main__":
    main()
