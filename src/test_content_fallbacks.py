#!/usr/bin/env python3
"""Regression tests for deterministic LinkedIn content fallbacks."""

from pathlib import Path

from generate_content import TOPIC_PLAN, ensure_truloop_website_slide, source_grounded_fallback

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
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 18 fallback slide {index} is missing required fields.")
        if not slide["title"] or not slide["body"] or not slide["visual_labels"]:
            raise SystemExit(f"Day 18 fallback slide {index} has empty title, body, or visual labels.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 18 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide["title"].split()) <= 7:
            raise SystemExit(f"Day 18 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide["body"].split()) <= 18:
            raise SystemExit(f"Day 18 fallback slide {index} body must contain 5-18 words.")
        layouts.add(slide["layout"])

    if sum(slide.get("visual_type") == "website" for slide in slides) != 1:
        raise SystemExit("Day 18 TruLoop fallback must contain exactly one genuine website slide.")
    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 18 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    capture_source = Path("src/capture_truloop_site.py").read_text(encoding="utf-8")
    if f'"{TOPIC}"' not in capture_source:
        raise SystemExit("Day 18 must be explicitly allowed by the verified TruLoop website-capture guard.")
    # One occurrence is the plan entry; the other three are fallback-routing sets.
    if source.count(f'"{TOPIC}",') != 4:
        raise SystemExit("Day 18 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 18 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")
    validate_day9()
    validate_day13()
    validate_day19()


def validate_day19():
    topic = "Keeping product ratings current after a new review"
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == topic]
    if len(matches) != 1:
        raise SystemExit("Day 19 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(topic)
    if data.get("topic") != topic:
        raise SystemExit("Day 19 fallback returned the wrong topic.")
    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 19 fallback must contain 70-95 words; got {word_count}.")
    paragraphs = [paragraph for paragraph in post.split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(f"Day 19 fallback must contain exactly three paragraphs; got {len(paragraphs)}.")
    for field in ("averageRating", "reviewCount"):
        if field not in post:
            raise SystemExit(f"Day 19 fallback must mention the verified {field} field.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 19 fallback must contain exactly five slides.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 19 fallback slide {index} is missing required fields.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 19 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide.get("title", "").split()) <= 7:
            raise SystemExit(f"Day 19 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide.get("body", "").split()) <= 18:
            raise SystemExit(f"Day 19 fallback slide {index} body must contain 5-18 words.")
        if not slide.get("visual_labels"):
            raise SystemExit(f"Day 19 fallback slide {index} needs visual labels.")
        layouts.add(slide["layout"])

    if sum(slide.get("visual_type") == "website" for slide in slides) != 1:
        raise SystemExit("Day 19 TruLoop fallback must contain exactly one genuine website slide.")
    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 19 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    capture_source = Path("src/capture_truloop_site.py").read_text(encoding="utf-8")
    if f'"{topic}"' not in capture_source:
        raise SystemExit("Day 19 must be allowed by the verified TruLoop screenshot-capture guard.")
    if source.count(f'"{topic}",') != 4:
        raise SystemExit("Day 19 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 19 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")
    validate_day20()



def validate_day20():
    topic = "Organizing Truloop's routes by responsibility"
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == topic]
    if len(matches) != 1:
        raise SystemExit("Day 20 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(topic)
    if data.get("topic") != topic:
        raise SystemExit("Day 20 fallback returned the wrong topic.")
    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 20 fallback must contain 70-95 words; got {word_count}.")
    paragraphs = [paragraph for paragraph in post.split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(f"Day 20 fallback must contain exactly three paragraphs; got {len(paragraphs)}.")
    for fact in ("product information", "product reviews", "authentication", "uploads", "admin"):
        if fact not in post.casefold():
            raise SystemExit(f"Day 20 fallback must mention the verified route area: {fact}.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 20 fallback must contain exactly five slides.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 20 fallback slide {index} is missing required fields.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 20 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide.get("title", "").split()) <= 7:
            raise SystemExit(f"Day 20 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide.get("body", "").split()) <= 18:
            raise SystemExit(f"Day 20 fallback slide {index} body must contain 5-18 words.")
        if not slide.get("visual_labels"):
            raise SystemExit(f"Day 20 fallback slide {index} needs visual labels.")
        layouts.add(slide["layout"])

    if sum(slide.get("visual_type") == "website" for slide in slides) != 1:
        raise SystemExit("Day 20 TruLoop fallback must contain exactly one genuine website slide.")
    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 20 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    capture_source = Path("src/capture_truloop_site.py").read_text(encoding="utf-8")
    if f'"{topic}"' not in capture_source:
        raise SystemExit("Day 20 must be allowed by the verified TruLoop screenshot-capture guard.")
    if source.count(f'"{topic}",') != 4:
        raise SystemExit("Day 20 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 20 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")
    validate_day21()


def validate_day21():
    topic = "Iterating on Truloop with Git"
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == topic]
    if len(matches) != 1:
        raise SystemExit("Day 21 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(topic)
    if data.get("topic") != topic:
        raise SystemExit("Day 21 fallback returned the wrong topic.")
    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 21 fallback must contain 70-95 words; got {word_count}.")
    paragraphs = [paragraph for paragraph in post.split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(f"Day 21 fallback must contain exactly three paragraphs; got {len(paragraphs)}.")
    for fact in ("Git for version control", "iterative development", "frontend, backend, and scratch folders", "commit history"):
        if fact not in post:
            raise SystemExit(f"Day 21 fallback must preserve the verified source fact: {fact}.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 21 fallback must contain exactly five slides.")

    if sum(slide.get("visual_type") == "website" for slide in slides) != 1:
        raise SystemExit("Day 21 TruLoop fallback must contain exactly one genuine website slide.")

    generated_without_website = [dict(slide) for slide in slides]
    website_index = next(
        index for index, slide in enumerate(generated_without_website)
        if slide.get("visual_type") == "website"
    )
    generated_without_website[website_index]["visual_type"] = "git"
    recovered_slides, used_fallback = ensure_truloop_website_slide(topic, generated_without_website)
    if not used_fallback or recovered_slides != slides:
        raise SystemExit("Day 21 must replace a generated slide set missing its website visual with the verified fallback.")
    unchanged_slides, used_fallback = ensure_truloop_website_slide(topic, slides)
    if used_fallback or unchanged_slides != slides:
        raise SystemExit("A valid Day 21 slide set must not be replaced unnecessarily.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 21 fallback slide {index} is missing required fields.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 21 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide.get("title", "").split()) <= 7:
            raise SystemExit(f"Day 21 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide.get("body", "").split()) <= 18:
            raise SystemExit(f"Day 21 fallback slide {index} body must contain 5-18 words.")
        labels = slide.get("visual_labels", [])
        if not 2 <= len(labels) <= 4:
            raise SystemExit(f"Day 21 fallback slide {index} must contain 2-4 visual labels.")
        layouts.add(slide.get("layout"))

    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 21 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    if source.count(f'"{topic}",') != 4:
        raise SystemExit("Day 21 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 21 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")
    validate_day22()


def validate_day22():
    topic = "Why the TechFest site was built as an alternative to Google Forms"
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == topic]
    if len(matches) != 1:
        raise SystemExit("Day 22 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(topic)
    if data.get("topic") != topic:
        raise SystemExit("Day 22 fallback returned the wrong topic.")

    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 22 fallback must contain 70-95 words; got {word_count}.")
    paragraph_separator = chr(10) * 2
    paragraphs = [paragraph for paragraph in post.split(paragraph_separator) if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(
            f"Day 22 fallback must contain exactly three paragraphs; got {len(paragraphs)} "
            f"with {post.count(paragraph_separator)} blank-line separators."
        )
    for fact in ("registration website", "Google Forms", "frontend developer volunteer",
                 "National Post Graduate College", "December 2024", "February 2025"):
        if fact.casefold() not in post.casefold():
            raise SystemExit(f"Day 22 fallback must preserve the verified source fact: {fact}.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 22 fallback must contain exactly five slides.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form",
                            "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 22 fallback slide {index} is missing required fields.")
        if not slide.get("title") or not slide.get("body") or not slide.get("visual_labels"):
            raise SystemExit(f"Day 22 fallback slide {index} has empty title, body, or visual labels.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 22 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide["title"].split()) <= 7:
            raise SystemExit(f"Day 22 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide["body"].split()) <= 18:
            raise SystemExit(f"Day 22 fallback slide {index} body must contain 5-18 words.")
        if not 2 <= len(slide["visual_labels"]) <= 4:
            raise SystemExit(f"Day 22 fallback slide {index} must contain 2-4 visual labels.")
        layouts.add(slide["layout"])

    if any(slide.get("visual_type") == "website" for slide in slides):
        raise SystemExit("Day 22 TechFest fallback must not use the TruLoop website screenshot.")
    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 22 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    if source.count(f'"{topic}"') != 5:
        raise SystemExit("Day 22 must appear in the plan, direct route, fallback function, and both fallback guards.")

    print(f"Day 22 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")


def validate_day9():
    topic = "The problem Truloop is designed to address"
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == topic]
    if len(matches) != 1:
        raise SystemExit("Day 9 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(topic)
    if data.get("topic") != topic:
        raise SystemExit("Day 9 fallback returned the wrong topic.")
    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 9 fallback must contain 70-95 words; got {word_count}.")
    paragraphs = [paragraph for paragraph in post.split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(f"Day 9 fallback must contain exactly three paragraphs; got {len(paragraphs)}.")
    for fact in ("sponsored content", "fake or incentivized reviews", "honest, unbiased, real-world product reviews"):
        if fact not in post.casefold():
            raise SystemExit(f"Day 9 fallback must preserve the verified project fact: {fact}.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 9 fallback must contain exactly five slides.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 9 fallback slide {index} is missing required fields.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 9 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide.get("title", "").split()) <= 7:
            raise SystemExit(f"Day 9 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide.get("body", "").split()) <= 18:
            raise SystemExit(f"Day 9 fallback slide {index} body must contain 5-18 words.")
        if not slide.get("visual_labels"):
            raise SystemExit(f"Day 9 fallback slide {index} needs visual labels.")
        layouts.add(slide["layout"])

    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 9 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    if source.count(f'"{topic}",') != 4:
        raise SystemExit("Day 9 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 9 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")



def validate_day13():
    topic = "Separating Truloop's frontend and backend"
    matches = [entry for entry in TOPIC_PLAN if entry.get("topic") == topic]
    if len(matches) != 1:
        raise SystemExit("Day 13 must appear exactly once in TOPIC_PLAN.")

    data = source_grounded_fallback(topic)
    if data.get("topic") != topic:
        raise SystemExit("Day 13 fallback returned the wrong topic.")

    post = data.get("post", "")
    word_count = len(post.split())
    if not 70 <= word_count <= 95:
        raise SystemExit(f"Day 13 fallback must contain 70-95 words; got {word_count}.")
    paragraphs = [paragraph for paragraph in post.split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise SystemExit(f"Day 13 fallback must contain exactly three paragraphs; got {len(paragraphs)}.")
    for fact in ("Next.js", "Express", "frontend", "backend", "root README", "microservices"):
        if fact not in post:
            raise SystemExit(f"Day 13 fallback must preserve the verified project fact: {fact}.")

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise SystemExit("Day 13 fallback must contain exactly five slides.")
    slide_fields = {"title", "body", "visual_type", "layout", "visual_labels"}
    allowed_visual_types = {"chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"}
    layouts = set()
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not slide_fields.issubset(slide):
            raise SystemExit(f"Day 13 fallback slide {index} is missing required fields.")
        if slide.get("visual_type") not in allowed_visual_types:
            raise SystemExit(f"Day 13 fallback slide {index} uses an unsupported visual type.")
        if not 3 <= len(slide.get("title", "").split()) <= 7:
            raise SystemExit(f"Day 13 fallback slide {index} title must contain 3-7 words.")
        if not 5 <= len(slide.get("body", "").split()) <= 18:
            raise SystemExit(f"Day 13 fallback slide {index} body must contain 5-18 words.")
        if not slide.get("visual_labels"):
            raise SystemExit(f"Day 13 fallback slide {index} needs visual labels.")
        layouts.add(slide.get("layout"))

    if sum(slide.get("visual_type") == "website" for slide in slides) != 1:
        raise SystemExit("Day 13 fallback must contain exactly one genuine website visual.")
    if slides[0].get("layout") != "hero" or slides[-1].get("layout") != "closing" or len(layouts) != 5:
        raise SystemExit("Day 13 fallback must use five distinct layouts, starting with hero and ending with closing.")

    source = Path("src/generate_content.py").read_text(encoding="utf-8")
    if source.count(f'"{topic}",') != 4:
        raise SystemExit("Day 13 must be present in the plan and all three deterministic-fallback routing sets.")

    print(f"Day 13 deterministic fallback passed: {word_count} words, 3 paragraphs, 5 slides.")


if __name__ == "__main__":
    main()
