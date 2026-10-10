import base64
import io
import json
import os
import random
import sys
import time
from pathlib import Path

from google import genai, types
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
OUTPUT_FILE = ROOT / "linkedin_image.jpg"
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
IMAGE_SIZE = os.getenv("GEMINI_IMAGE_SIZE", "2K")
TARGET_EDGE = 2048
MAX_ATTEMPTS = 5
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def get_http_status(exc):
    for attribute in ("code", "status_code", "status"):
        value = getattr(exc, attribute, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def generate_with_retry(client, prompt):
    """Retry transient API errors. Never replace a failed illustration with a generic image."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return client.interactions.create(
                model=IMAGE_MODEL,
                input=prompt,
                response_format={
                    "type": "image",
                    "mime_type": "image/jpeg",
                    "aspect_ratio": "1:1",
                    "image_size": IMAGE_SIZE,
                },
            )
        except Exception as exc:
            status = get_http_status(exc)
            if status not in RETRYABLE_HTTP_CODES or attempt == MAX_ATTEMPTS - 1:
                raise
            delay = min(30, 2 ** (attempt + 1)) + random.uniform(0, 1)
            print(f"Image model temporarily returned HTTP {status}; retrying in {delay:.1f}s.")
            time.sleep(delay)


def build_image_prompt(data):
    topic = str(data.get("topic", "")).strip()
    brief = str(data.get("illustration_brief", "")).strip()
    facts = data.get("source_facts", [])
    if not topic or not brief or not isinstance(facts, list) or not facts:
        raise RuntimeError("content.json needs a topic, source facts, and an illustration brief.")

    facts_text = "\n".join(f"- {str(fact)}" for fact in facts)
    return f"""
Create ONE high-quality square editorial illustration for a LinkedIn post.

Topic: {topic}
Approved facts:
{facts_text}

Visual idea:
{brief}

Art direction:
- Make it look genuinely hand-drawn by an illustrator: deep ink contours, visible pencil marks, restrained colored-pencil shading, small watercolor or marker washes, and subtle warm paper grain.
- Use an editorial explainer illustration, not stock art. Make one clear visual idea the focal point, with only a few carefully chosen supporting objects.
- Preserve a tactile sketchbook quality with slightly imperfect linework, while keeping the finish polished and professional.
- Use a consistent limited palette of warm off-white, ink navy, muted teal, soft terracotta, and ochre.
- Keep meaningful objects within the central 82 percent of the canvas, with generous safe margins on every side. The full square composition must work in mobile, tablet, and desktop LinkedIn feeds.
- Use clear visual hierarchy, crisp details, ample negative space, and strong contrast so the idea remains readable at a small size.
- Do not include words, letters, numbers, captions, labels, logos, speech bubbles, watermarks, or signatures. Do not render the LinkedIn post copy inside the illustration.
- Do not use photorealism, glossy 3D, generic corporate stock art, collages, grids of panels, or decorative text.
- Do not add facts, product features, metrics, users, or claims that are absent from the approved facts.
- Return one standalone square illustration only.
"""


def main():
    api_key = os.getenv("GEMINI_IMAGE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_IMAGE_API_KEY or GEMINI_API_KEY is missing. "
            "Image generation requires a Gemini API key with image-model access."
        )
    if not CONTENT_FILE.is_file():
        raise FileNotFoundError("content.json is missing. Run src/generate_content.py first.")

    try:
        data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not read valid content.json.") from exc

    prompt = build_image_prompt(data)
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=120_000))

    print(f"Generating one {IMAGE_SIZE} square illustration with {IMAGE_MODEL}...")
    print("Style: hand-inked contours, colored pencil, watercolor washes, and paper texture.")

    with client:
        interaction = generate_with_retry(client, prompt)

    generated_image = getattr(interaction, "output_image", None)
    encoded_data = getattr(generated_image, "data", None) if generated_image else None
    if not encoded_data:
        raise RuntimeError(
            "Gemini returned no image data. No text-only fallback will be published."
        )

    try:
        image_bytes = base64.b64decode(encoded_data, validate=True)
        with Image.open(io.BytesIO(image_bytes)) as source_image:
            source_image.load()
            image = ImageOps.fit(
                source_image.convert("RGB"),
                (TARGET_EDGE, TARGET_EDGE),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
    except Exception as exc:
        raise RuntimeError("Gemini returned image data that could not be decoded.") from exc

    image.save(
        OUTPUT_FILE,
        format="JPEG",
        quality=93,
        subsampling=0,
        optimize=True,
        progressive=True,
    )

    with Image.open(OUTPUT_FILE) as verified:
        if verified.size != (TARGET_EDGE, TARGET_EDGE) or verified.format != "JPEG":
            raise RuntimeError("Final image failed its size or format validation.")

    size_bytes = OUTPUT_FILE.stat().st_size
    if size_bytes < 100 * 1024 or size_bytes > 12 * 1024 * 1024:
        raise RuntimeError(f"Illustration file size is outside the expected range: {size_bytes:,} bytes.")

    print(f"Illustration ready: {OUTPUT_FILE.name}")
    print(f"Dimensions: {TARGET_EDGE} x {TARGET_EDGE} pixels, square JPEG")
    print(f"File size: {size_bytes:,} bytes")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
