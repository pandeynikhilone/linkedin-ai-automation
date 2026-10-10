import json
import os
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

OUTPUT_FILE = Path("content.json")
PORTFOLIO_URL = "https://pandeynikhilone.github.io/"

# A 30-topic plan built from resume facts and public GitHub project details.
# The sequence starts on 2026-10-11, then repeats after 30 days.
TOPIC_PLAN = [
    {
        "topic": "My Techqueto internship: building charts in React",
        "facts": [
            "Resume: frontend developer intern at Techqueto Pvt Ltd. from December 2025 to January 2026.",
            "Built line, bar, area, and pie charts using React and Google Charts."
        ],
        "angle": "Describe the actual chart work and what the components displayed. Do not invent dashboard users or business outcomes."
    },
    {
        "topic": "Replacing hardcoded chart values with JSON-driven data",
        "facts": [
            "At Techqueto, chart data and configuration were moved to JSON-driven values instead of being hardcoded.",
            "The work used TypeScript, React, and Google Charts."
        ],
        "angle": "Explain this specific implementation choice. Do not claim measured improvements in speed or performance."
    },
    {
        "topic": "Why I created reusable chart utilities in common.ts",
        "facts": [
            "Resume: designed reusable chart utilities in common.ts for shared data and chart options."
        ],
        "angle": "Explain reuse and consistency in the context of this real task. Do not invent other functions or modules."
    },
    {
        "topic": "Loading chart data asynchronously with useEffect",
        "facts": [
            "Resume: integrated asynchronous data loading with proper useEffect usage in the React chart work at Techqueto."
        ],
        "angle": "Stay with the described React implementation. Do not invent a particular API endpoint or loading-state feature."
    },
    {
        "topic": "Debugging TypeScript and chart rendering issues",
        "facts": [
            "Resume: debugged TypeScript, data-shape, and rendering issues across multiple chart types at Techqueto."
        ],
        "angle": "Use the exact debugging areas listed. Do not invent a specific bug, incident, or resolution timeline."
    },
    {
        "topic": "Making chart components easier to extend",
        "facts": [
            "Resume: the chart work was designed to be backend-ready and easy to extend.",
            "The charts covered line, bar, area, and pie types."
        ],
        "angle": "Explain the stated intent without claiming the system was deployed to a particular customer or had a quantified impact."
    },
    {
        "topic": "The technologies I used during my frontend internship",
        "facts": [
            "Techqueto internship, December 2025 to January 2026.",
            "Resume lists TypeScript, React.js, and Google Charts for this role.",
            "Tasks included dynamic charts, JSON-driven configuration, reusable utilities, async loading, and debugging."
        ],
        "angle": "Summarize the real scope of the internship, not a fictional day-in-the-life story."
    },
    {
        "topic": "The problem Truloop is designed to address",
        "facts": [
            "Truloop README says sponsored posts and fake or incentivized reviews can make it difficult to find trustworthy product information.",
            "The project aims to emphasize honest, unbiased, real-world product reviews."
        ],
        "angle": "Describe the product motivation as stated in the README. Do not claim Truloop has eliminated fake reviews or proven market impact."
    },
    {
        "topic": "What Truloop means by real usage experience",
        "facts": [
            "Truloop README says reviews should be based on real usage experience.",
            "The README gives battery life and software stability as examples."
        ],
        "angle": "Explain the intended review focus. Do not invent reviews from actual named users."
    },
    {
        "topic": "Designing a product browsing and review flow",
        "facts": [
            "Truloop provides a growing product catalog, product specifications, in-depth user reviews, and a way for users to submit their own reviews, according to its README."
        ],
        "angle": "Describe the product flow at a high level without inventing user research or conversion results."
    },
    {
        "topic": "Building Truloop's frontend with Next.js App Router",
        "facts": [
            "Resume: built a responsive, component-based frontend using Next.js App Router and Tailwind CSS.",
            "The goal described in the resume was clean navigation and mobile-first design."
        ],
        "angle": "Discuss the actual frontend structure and responsive design focus."
    },
    {
        "topic": "Reusable navigation, product cards, and review sections",
        "facts": [
            "Resume: built reusable UI components including navigation menus, product cards, and review sections in Truloop."
        ],
        "angle": "Explain the purpose of reusable components in this project. Do not invent design-system metrics."
    },
    {
        "topic": "Separating Truloop's frontend and backend",
        "facts": [
            "Truloop repository has a Next.js frontend folder and an Express backend folder.",
            "The root README describes running the frontend and backend together or separately."
        ],
        "angle": "Describe the actual project structure, not a claim that the architecture is microservices."
    },
    {
        "topic": "Connecting Truloop's interface to backend APIs",
        "facts": [
            "Resume: integrated Node.js and Express.js backend APIs to manage products, reviews, and user interactions."
        ],
        "angle": "Stay with these three areas. Do not invent API traffic, latency, or endpoint counts."
    },
    {
        "topic": "Structuring review data with MongoDB",
        "facts": [
            "Resume: structured MongoDB schemas to support review data, user submissions, and authentication workflows."
        ],
        "angle": "Explain the data areas supported by the schema. Do not invent table counts or database scale."
    },
    {
        "topic": "A look at Truloop's receipt proof validation",
        "facts": [
            "GitHub source backend/src/services/proofValidator.js uses Tesseract.js for OCR on image files and pdf-parse for PDFs.",
            "The code checks extracted text for receipt-related terms and a match with the product name.",
            "The validation is a text-based check, not a guarantee of genuine purchase."
        ],
        "angle": "Be transparent that this is the current implementation logic and avoid calling it foolproof or fraud-proof."
    },
    {
        "topic": "Checking purchase dates against product release dates",
        "facts": [
            "GitHub source in backend/src/controllers/review.controller.js rejects a purchase date earlier than a product's release date when both dates are present."
        ],
        "angle": "Explain the specific validation rule and why dates need validation. Do not claim wider fraud prevention."
    },
    {
        "topic": "Validating the data required to submit a Truloop review",
        "facts": [
            "GitHub review controller requires productId, rating, comment, reviewer, usageDuration, and recommend before creating a review."
        ],
        "angle": "Describe the real review-submission validation. Do not invent other required fields."
    },
    {
        "topic": "Keeping product ratings current after a new review",
        "facts": [
            "GitHub review controller retrieves a product's reviews, calculates the average rating, updates averageRating and reviewCount, and saves the product after review creation."
        ],
        "angle": "Explain how the current code updates aggregates. Do not claim benchmarks or production volume."
    },
    {
        "topic": "Organizing Truloop's routes by responsibility",
        "facts": [
            "GitHub has separate frontend routes for products, product information, product reviews, submit review, profile, and authentication.",
            "Backend source has distinct route files for auth, products, reviews, uploads, and admin."
        ],
        "angle": "Explain how the repository organizes areas of responsibility without claiming perfect separation or comprehensive test coverage."
    },
    {
        "topic": "Iterating on Truloop with Git",
        "facts": [
            "Resume: used Git for version control and iterative development to enhance features and architecture.",
            "GitHub repository shows separate frontend, backend, and scratch folders, with a recorded commit history."
        ],
        "angle": "Discuss the documented iterative process. Do not invent specific teamwork rituals or pull-request statistics."
    },
    {
        "topic": "Why the TechFest site was built as an alternative to Google Forms",
        "facts": [
            "TechFest README describes a registration website built to offer students an alternative to traditional forms such as Google Forms.",
            "Resume identifies Nikhil as frontend developer volunteer for National Post Graduate College, December 2024 to February 2025."
        ],
        "angle": "Describe the project's purpose and your documented frontend role."
    },
    {
        "topic": "Helping students browse and choose a TechFest event",
        "facts": [
            "TechFest README lists student registration and event selection as features."
        ],
        "angle": "Explain the registration journey based only on the documented features."
    },
    {
        "topic": "Making manual payment details clearer in TechFest",
        "facts": [
            "TechFest README lists a manual payment method with an organized summary and detailed information."
        ],
        "angle": "Describe the feature as implemented in the project README. Do not imply online payment gateway integration."
    },
    {
        "topic": "Generating an admit card after payment in TechFest",
        "facts": [
            "TechFest README lists an admit card after successful payment as a project feature."
        ],
        "angle": "Explain the stated user flow and do not invent QR codes, email delivery, or verification features."
    },
    {
        "topic": "The actual stack behind the TechFest registration project",
        "facts": [
            "TechFest README lists HTML, CSS, JavaScript, and Bootstrap for frontend, Django for backend, and SQLite for the database.",
            "The README credits Nikhil Pandey as frontend developer and Dev Athwani as backend developer."
        ],
        "angle": "Credit the documented roles accurately. Do not present the whole backend as Nikhil's individual work."
    },
    {
        "topic": "What supporting registration for 8,000-plus students involved",
        "facts": [
            "Resume: supported live event operations by handling registrations for over 8,000 students during the TechFest.",
            "Resume: tested and refined UI behaviour for diverse inputs under time constraints."
        ],
        "angle": "Use the 8,000-plus number exactly as in the resume. Do not claim requests per second, uptime, or individual ownership of the full system."
    },
    {
        "topic": "Testing forms with different inputs and time constraints",
        "facts": [
            "Resume: tested and refined the TechFest user interface for diverse user inputs under time constraints."
        ],
        "angle": "Discuss the documented testing responsibility without inventing a specific bug or test count."
    },
    {
        "topic": "My documented work across charts, reviews, and registration",
        "facts": [
            "Resume lists a frontend internship at Techqueto focused on React, TypeScript, and Google Charts.",
            "Resume lists Truloop as a full-stack product review platform using Next.js, React, Tailwind CSS, Node.js, Express, and MongoDB.",
            "Resume lists frontend volunteer work on a TechFest registration platform for over 8,000 students.",
            "Resume records 200-plus GitHub contributions."
        ],
        "angle": "Connect only these documented areas of work. Do not claim the 200-plus contributions occurred in a particular time period."
    },
    {
        "topic": "Keeping my contribution clear on a collaborative project",
        "facts": [
            "TechFest README credits Nikhil Pandey as frontend developer and Dev Athwani as backend developer.",
            "The resume describes Nikhil's role as frontend developer volunteer at National Post Graduate College from December 2024 to February 2025.",
            "TechFest README lists HTML, CSS, JavaScript, and Bootstrap for frontend, Django for backend, and SQLite for the database."
        ],
        "angle": "Explain the importance of accurately describing project roles. Do not claim sole ownership of the backend or the entire project."
    }
]

PLAN_START_DATE = date(2026, 10, 11)

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

    # Keep the 30-day personal work series in a stable order, starting
    # on the next scheduled publication date. After day 30 it cycles again.
    today = datetime.now(ZoneInfo("Asia/Kolkata"))
    elapsed_days = max(0, (today.date() - PLAN_START_DATE).days)
    topic_index = elapsed_days % len(TOPIC_PLAN)
    selected_topic = TOPIC_PLAN[topic_index]
    topic = selected_topic["topic"]
    source_facts = "\n".join(f"- {fact}" for fact in selected_topic["facts"])
    post_angle = selected_topic["angle"]
    include_portfolio_cta = today.date().toordinal() % 3 == 0
    portfolio_cta_instruction = (
        f"If it fits naturally, end with a brief invitation to see project work at {PORTFOLIO_URL}. Include the URL exactly once."
        if include_portfolio_cta
        else "Do not add a portfolio URL or self-promotional call to action today."
    )

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    prompt = f"""
Write one LinkedIn post and an accompanying animated-slide video outline
based only on Nikhil Pandey's actual resume and public GitHub project details.

Today's topic: {topic}
Verified source facts for this topic:
{source_facts}

Angle for this post: {post_angle}

Rules:
- Write approximately 100-180 words in a natural voice that sounds like an MCA student describing real software work, not a marketing agency or an AI assistant.
- Anchor the post in the specific project, task, or implementation details above. Do not substitute generic career advice or motivational filler.
- You may write in first person only for contributions explicitly attributed to Nikhil in the facts. Credit collaborator/backend work accurately where specified.
- Do not invent personal feelings, conversations, incidents, difficulties, fixes, outcomes, users, metrics, project features, technical decisions, or reasons not present in the source facts.
- Do not turn the current proof-validation implementation into a claim of guaranteed or fraud-proof verification.
- Do not claim Truloop has achieved adoption or business results beyond what the source facts state.
- Do not invent projects, internship experiences, achievements, dates, statistics, certifications, or engagement numbers.
- Create exactly 5 concise, mobile-readable slides that reinforce the same verified topic. Slides must not introduce facts absent from the source facts.
- Include 3-5 relevant hashtags, separate from the post body.
- The post, hashtags, video title, and slides must all match today's topic and source facts.
- Portfolio CTA instruction for today: {portfolio_cta_instruction}
- Return only data matching the supplied JSON schema.
"""

    print(
        f"Generating day {topic_index + 1}/{len(TOPIC_PLAN)} "
        f"for {today.date()}: {topic}"
    )
    print("Source facts used for this post:")
    print(source_facts)

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
