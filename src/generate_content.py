
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

OUTPUT_FILE = Path("content.json")

TOPICS = [
    "How to turn daily learning into credible proof of skill",
    "How students can describe projects honestly on a resume",
    "Preparing for internships without exaggerating experience",
    "Why documenting mistakes helps you learn faster",
    "Building a sustainable weekly learning plan",
    "Demonstrating communication skills in technical roles",
    "Reviewing progress and setting useful goals",
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


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to GitHub Actions secrets."
        )

    # Choose a topic based on the date in India.
    today = datetime.now(ZoneInfo("Asia/Kolkata"))
    topic = TOPICS[today.weekday()]

    client = genai.Client(api_key=api_key)
    prompt = f"""
Create one original LinkedIn post and an accompanying animated-slide
video outline for a student documenting career growth, internship
preparation, and learning in public.

Today's topic: {topic}

Rules:
- Write a useful, professional LinkedIn post of approximately
  100-180 words.
- Start with a clear hook and give practical advice.
- Use a natural, thoughtful tone, not generic motivational language.
- Create exactly 5 video slides, each with a short title and
  concise body text suitable for a mobile screen.
- Make the slides useful even when watched without sound.
- Include 3-5 relevant hashtags without putting them inside the post.
- Do not invent projects, internship experiences, achievements,
  statistics, certifications, or personal stories.
- Do not claim the author personally did something unless that
  fact is provided. Prefer honest educational reflections.
- The post and slides must teach the same central lesson.
- Return only data matching the supplied JSON schema.
"""

    print(f"Generating content about: {topic}")

    with client:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": SCHEMA,
            },
        )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Gemini did not return valid JSON."
        ) from exc

    # Basic validation before passing content to later workflow steps.
    required = {"topic", "post", "hashtags", "video_title", "slides"}
    if not required.issubset(data):
        raise RuntimeError("Generated content is missing required fields.")

    if not isinstance(data["post"], str) or not data["post"].strip():
        raise RuntimeError("Generated LinkedIn post is empty.")

    if not isinstance(data["slides"], list) or len(data["slides"]) != 5:
        raise RuntimeError("Expected exactly 5 slides.")

    for slide in data["slides"]:
        if not slide.get("title") or not slide.get("body"):
            raise RuntimeError("A slide is missing its title or body.")

    OUTPUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Success: generated the post and {len(data['slides'])} slides.")
    print(f"Saved to {OUTPUT_FILE}")
    print("\nPost preview:\n")
    print(data["post"])
    print("\nHashtags:", " ".join(data["hashtags"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
