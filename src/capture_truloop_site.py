#!/usr/bin/env python3
"""Capture genuine screenshots from the deployed TruLoop application for video scenes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
ASSET_DIR = ROOT / "generated_assets"
HOME_URL = "https://truloop.vercel.app/"

SCREEN_ROUTES = {
    "homepage": ("/", "truloop_homepage.png", True),
    "products": ("/products", "truloop_products.png", False),
    "submit_review": ("/submit-review", "truloop_submit_review.png", False),
    "add_review": ("/add-review", "truloop_add_review.png", False),
    "login": ("/auth/login", "truloop_login.png", False),
    "register": ("/auth/register", "truloop_register.png", False),
    "profile": ("/profile", "truloop_profile.png", False),
}


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

    topic = str(content.get("topic", "")).strip()
    verified_truloop_topics = {
        "Designing a product browsing and review flow",
    }
    if "truloop" not in topic.casefold() and topic not in verified_truloop_topics:
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

            for _, (route, filename, required) in SCREEN_ROUTES.items():
                capture(page, urljoin(HOME_URL, route), ASSET_DIR / filename, required=required)

            # Capture a real catalogue-linked detail page and its review section, if present.
            products_url = urljoin(HOME_URL, "/products")
            try:
                response = page.goto(products_url, wait_until="domcontentloaded", timeout=60_000)
                if response is not None and response.status < 400:
                    settle_page(page)
                    link = page.locator('a[href*="/product-info/"]').first
                    if link.count():
                        href = link.get_attribute("href")
                        if href:
                            target = urljoin(HOME_URL, href)
                            path = urlparse(target).path
                            match = re.search(r"/product-info/([^/?#]+)", path)
                            if match:
                                detail_url = urljoin(HOME_URL, f"/product-info/{match.group(1)}")
                                capture(page, detail_url, ASSET_DIR / "truloop_product_detail.png")
                                capture(page, detail_url.rstrip("/") + "/reviews",
                                        ASSET_DIR / "truloop_product_reviews.png")
            except Exception as exc:
                print(f"Optional product detail and review capture skipped: {exc}")
        finally:
            browser.close()

    if not (ASSET_DIR / "truloop_homepage.png").is_file():
        raise SystemExit("The real TruLoop homepage screenshot is required but was not captured.")
    print("TruLoop screenshot capture finished. Only screens that loaded successfully are retained.")


if __name__ == "__main__":
    main()
