import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

OUTPUT_FILE = Path("content.json")

# A 30-topic evergreen rotation. Indexing by date avoids repeating the
# same topic every Monday, Tuesday, etc. No personal claims are invented.
TOPICS = [
    "How to turn daily learning into credible proof of skill",
    "How students can describe projects honestly on a resume",
    "Preparing for internships without exaggerating experience",
    "Why documenting mistakes helps you learn faster",
    "Building a sustainable weekly learning plan",
    "Demonstrating communication skills in technical roles",
    "Reviewing progress and setting useful goals",
    "Designing a README that helps another developer understand a project",
    "Explaining a technical trade-off in plain language",
    "Breaking a feature into small, testable tasks",
    "Debugging systematically instead of guessing",
    "Writing commit messages that explain intent",
    "Creating a simple internship application tracker",
    "Writing a useful project case study",
    "Finishing one focused project instead of starting too many",
    "Discussing challenges without overstating your contribution",
    "Turning a classroom concept into a small practical project",
    "Using tests to make software changes safer",
    "Learning branches and pull requests through practice",
    "Preparing concise answers for technical screening questions",
    "Explaining an API integration as a sequence of steps",
    "Making a developer portfolio easy for recruiters to scan",
    "Describing your exact contribution to a team project",
    "Practising SQL and documenting why a query works",
    "Communicating uncertainty clearly in engineering work",
    "Planning one focused DSA revision session",
    "Comparing two implementation approaches fairly",
    "Why a working demo strengthens a project portfolio",
    "Writing a reproducible bug report",
    "Reviewing learning progress without vanity metrics",
]

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic": {"type": "STRING"},
        "post": {"type": "STRING"},
        "hashtags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "video_title": {"type": "STRING"},
        "slides": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "body": {"type": "STRING"},
                },
                "required": ["title", "body"],
            },
        },
    },
    "required": ["topic", "post", "hashtags", "video_title", "slides"],
}

RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


def get_http_status(exc):
    """Read an HTTP status from common Google GenAI SDK exception shapes."""
    for attribute in ("code", "status_code", "status"):
        value = getattr(exc, attribute, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            digits = value.strip()
            if digits.isdigit():
                return int(digits)

    return None


def generate_with_retry(client, model, prompt):
    """Retry only transient service, rate-limit, and gateway errors."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": SCHEMA,
                },
            )
        except Exception as exc:
            status = get_http_status(exc)
            if status not in RETRYABLE_HTTP_CODES or attempt == MAX_ATTEMPTS - 1:
                raise

            # Exponential backoff with jitter: approximately 2, 4, 8, 16 seconds.
            delay = min(30, 2 ** (attempt + 1)) + random.uniform(0, 1)
            print(
                f"Gemini temporarily returned HTTP {status}; "
                f"attempt {attempt + 1}/{MAX_ATTEMPTS - 1} failed. "
                f"Retrying in {delay:.1f}s."
            )
            time.sleep(delay)


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to GitHub Actions secrets."
        )

    # Use India's local date so topic rotation matches the publication ledger.
    today = datetime.now(ZoneInfo("Asia/Kolkata"))
    topic_index = today.date().toordinal() % len(TOPICS)
    topic = TOPICS[topic_index]

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    prompt = f"""
Create one original LinkedIn post and an accompanying animated-slide
video outline for a student documenting career growth, internship
preparation, software development, and learning in public.

Today's topic: {topic}

Rules:
- Write a useful, professional LinkedIn post of approximately 100-180 words.
- Start with a clear hook and give practical advice.
- Use a natural, thoughtful tone, not generic motivational language.
- Create exactly 5 video slides, each with a short title and concise body
  suitable for a mobile screen.
- Make the slides useful even when watched without sound.
- Include 3-5 relevant hashtags without putting them inside the post.
- Do not invent projects, internship experiences, achievements, statistics,
  certifications, engagement numbers, or personal stories.
- Do not claim the author personally did something unless that fact is provided.
- Prefer useful educational reflections and actionable examples.
- The post and slides must teach the same central lesson.
- Return only data matching the supplied JSON schema.
"""

    print(
        f"Generating topic {topic_index + 1}/{len(TOPICS)} "
        f"for {today.date()}: {topic}"
    )

    with client:
        response = generate_with_retry(client, model, prompt)

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini did not return valid JSON.") from exc

    required = {"topic", "post", "hashtags", "video_title", "slides"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise RuntimeError("Generated content is missing required fields.")

    if not isinstance(data["post"], str) or not data["post"].strip():
        raise RuntimeError("Generated LinkedIn post is empty.")

    if not isinstance(data["video_title"], str) or not data["video_title"].strip():
        raise RuntimeError("Generated video title is empty.")

    if not isinstance(data["hashtags"], list):
        raise RuntimeError("Generated hashtags must be a list.")

    if not isinstance(data["slides"], list) or len(data["slides"]) != 5:
        raise RuntimeError("Expected exactly 5 slides.")

    for slide in data["slides"]:
        if not isinstance(slide, dict) or not slide.get("title") or not slide.get("body"):
            raise RuntimeError("A slide is missing its title or body.")

    OUTPUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Success: generated the post and {len(data['slides'])} slides.")
    print(f"Saved to {OUTPUT_FILE}")
    print("\nPost preview:\n")
    print(data["post"])
    print("\nHashtags:", " ".join(f"#{str(tag).lstrip('#')}" for tag in data["hashtags"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
