#!/usr/bin/env python3
"""Regression tests for deterministic LinkedIn content fallbacks."""

from pathlib import Path

from generate_content import TOPIC_PLAN, source_grounded_fallback

TOPIC = "Validating the data required to submit a Truloop review"
REQUIRED_FIELDS = ("productId", "rating", "comment", "reviewer", "usageDuration", "recommend")


def main():
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == TOPIC]
    if len(matches) != 1:
        raise SystemExit("Day 18 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(TOPIC)
    if data.get("topic") != TOPIC:
        raise SystemExit("Fallback returned the wrong topic.")

    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 18 fallback must contain 70-95 words; got {word_count}.")
    paragraphs = [paragraph for paragraph in post.split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(f"Day 18 fallback must contain exactly three paragraphs; got {len(paragraphs)}.")
    if not all(field in post for field in REQUIRED_FIELDS):
        raise SystemExit("Day 18 fallback must name all six verified required review fields.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 18 fallback must contain exactly five slides.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 18 fallback slide {index} is missing required fields.")
        if not slide["title"] or not slide["body"] or not slide["visual_labels"]:
            raise SystemExit(f"Day 18 fallback slide {index} has empty title, body, or visual labels.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    # One occurrence is the plan entry; the other three are fallback-routing sets.
    if source.count(f'"{TOPIC}",') != 4:
        raise SystemExit("Day 18 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 18 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")


if __name__ == "__main__":
    main()
