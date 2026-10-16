#!/usr/bin/env python3
"""Capture real deployed TruLoop screens for video frames that need website footage."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
ASSET_DIR = ROOT / "generated_assets"
HOME_URL = "https://truloop.vercel.app/"
PRODUCTS_URL = urljoin(HOME_URL, "products")
HOME_SCREENSHOT = ASSET_DIR / "truloop_homepage.png"
PRODUCTS_SCREENSHOT = ASSET_DIR / "truloop_products.png"
DETAIL_SCREENSHOT = ASSET_DIR / "truloop_product_detail.png"


def settle_page(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=12_000)
    except PlaywrightTimeoutError:
        # Client side apps can keep requests open after the visible page is ready.
        pass
    try:
        page.evaluate("() => document.fonts.ready")
    except Exception:
        pass


def capture(page, url: str, output_path: Path, required: bool = False) -> bool:
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if response is not None and response.status >= 400:
            raise RuntimeError(f"HTTP {response.status} while opening {url}")
        settle_page(page)
        page.screenshot(path=str(output_path), full_page=False, animations="disabled")
        if not output_path.is_file() or output_path.stat().st_size < 15_000:
            raise RuntimeError(f"Screenshot for {url} is missing or unexpectedly small.")
        print(f"Captured {url} -> {output_path.name} ({output_path.stat().st_size:,} bytes).")
        return True
    except Exception as exc:
        if required:
            raise RuntimeError(f"Could not capture the deployed TruLoop homepage: {exc}") from exc
        print(f"Optional TruLoop screen skipped for {url}: {exc}")
        return False


def main() -> None:
    if not CONTENT_FILE.is_file():
        raise SystemExit("content.json is missing. Generate the post before capturing the site.")

    content = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    slides = content.get("slides", [])
    needs_site = any(
        isinstance(slide, dict) and slide.get("visual_type") == "website"
        for slide in slides
    )
    if not needs_site:
        print("No live website visual requested for this topic; screenshot capture skipped.")
        return

    if "truloop" not in str(content.get("topic", "")).casefold():
        raise SystemExit("The website visual is reserved for verified TruLoop content.")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 1180, "height": 780},
                device_scale_factor=1,
                color_scheme="light",
                reduced_motion="reduce",
            )
            capture(page, HOME_URL, HOME_SCREENSHOT, required=True)

            if capture(page, PRODUCTS_URL, PRODUCTS_SCREENSHOT):
                # Prefer a real detail page linked from the live catalogue.
                try:
                    product_link = page.locator('a[href*="/product-info/"]').first
                    if product_link.count():
                        href = product_link.get_attribute("href")
                        if href:
                            capture(page, urljoin(HOME_URL, href), DETAIL_SCREENSHOT)
                except Exception as exc:
                    print(f"Optional product detail capture skipped: {exc}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
