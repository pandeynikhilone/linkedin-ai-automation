#!/usr/bin/env python3
"""Capture the genuine deployed TruLoop homepage for video frames that need it."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
OUTPUT_FILE = ROOT / "generated_assets" / "truloop_homepage.png"
SITE_URL = "https://truloop.vercel.app/"


def main() -> None:
    if not CONTENT_FILE.is_file():
        raise SystemExit("content.json is missing. Generate the post before capturing the site.")

    content = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    slides = content.get("slides", [])
    if not any(isinstance(slide, dict) and slide.get("visual_type") == "website" for slide in slides):
        print("No live website visual requested for this topic; screenshot capture skipped.")
        return

    if "truloop" not in str(content.get("topic", "")).casefold():
        raise SystemExit("The website visual is reserved for verified TruLoop content.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 1440, "height": 920},
                device_scale_factor=1,
                color_scheme="light",
                reduced_motion="reduce",
            )
            response = page.goto(SITE_URL, wait_until="domcontentloaded", timeout=60_000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f"TruLoop returned HTTP {response.status} at {SITE_URL}.")
            try:
                page.wait_for_load_state("networkidle", timeout=12_000)
            except PlaywrightTimeoutError:
                # Some client side apps keep network connections open. A rendered page is still usable.
                pass
            try:
                page.evaluate("() => document.fonts.ready")
            except Exception:
                pass
            page.screenshot(path=str(OUTPUT_FILE), full_page=False, animations="disabled")
        finally:
            browser.close()

    if not OUTPUT_FILE.is_file() or OUTPUT_FILE.stat().st_size < 15_000:
        raise SystemExit("The captured TruLoop screenshot is missing or unexpectedly small.")
    print(f"Captured genuine deployed TruLoop page: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size:,} bytes).")


if __name__ == "__main__":
    main()
