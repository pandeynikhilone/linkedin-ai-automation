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

# The 30-topic plan below is grounded in the resume and public GitHub repositories.
# The sequence starts on 2026-10-11 and repeats after 30 days.
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
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
        "illustration_brief": {"type": "STRING"},
    },
    "required": ["topic", "post", "hashtags", "illustration_brief"],
}

RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


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


def generate_with_retry(client, model, prompt):
    """Retry temporary API overloads without inventing fallback content."""
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
            delay = min(30, 2 ** (attempt + 1)) + random.uniform(0, 1)
            print(f"Gemini temporarily returned HTTP {status}; retrying in {delay:.1f}s.")
            time.sleep(delay)


def clean_hashtags(values):
    hashtags = []
    seen = set()
    for value in values:
        tag = "".join(
            character
            for character in str(value).strip().lstrip("#")
            if character.isalnum() or character == "_"
        )
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            hashtags.append(tag)
    return hashtags[:4]


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to GitHub Actions secrets.")

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

    prompt = f"""
Write one concise LinkedIn post and a visual brief for a single editorial illustration.
Base everything only on Nikhil Pandey's actual resume and public GitHub project details.

Today's topic: {topic}
Verified source facts:
{source_facts}

Angle for this post: {post_angle}

Writing style and formatting:
- Aim for 70 to 95 words. The post body must not exceed 110 words.
- Sound like an MCA student or early-career developer describing real work in a clear, grounded way. Do not sound like a corporate marketer or AI assistant.
- Start with one specific, natural opening line.
- Use short paragraphs separated by blank lines. If it helps explain the actual implementation, use at most 3 short bullet points beginning with "• ".
- End with one concise takeaway. Avoid generic motivation, filler, exaggerated claims, fake excitement, and engagement bait.
- Do not invent personal feelings, conversations, incidents, difficulties, fixes, outcomes, users, metrics, features, technical decisions, dates, or reasons that are absent from the facts.
- Use first person only for contributions explicitly attributed to Nikhil. Credit collaborators accurately.
- Do not describe Truloop's receipt-validation code as guaranteed proof of purchase or fraud-proof.
- Do not use long dash punctuation. Use ordinary punctuation and short sentences.
- Return 3 or 4 relevant hashtags separately from the post body.

Illustration brief:
- Describe one simple, specific visual metaphor or explanatory scene that helps a reader understand today's topic.
- The illustration will be rendered separately as a hand-drawn editorial illustration. Do not ask for text, letters, numbers, labels, captions, logos, watermarks, or a collage.
- Use only visual facts compatible with the verified facts. Do not invent product features, users, metrics, or business results.
- Keep the main visual simple and readable at mobile-feed size.

Portfolio CTA instruction: {portfolio_cta_instruction}

Return only JSON with these fields: topic, post, hashtags, illustration_brief.
"""

    print(f"Generating day {topic_index + 1}/{len(TOPIC_PLAN)} for {today.date()}: {topic}")
    print("Verified source facts:")
    print(source_facts)

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    with client:
        response = generate_with_retry(client, model, prompt)

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini did not return valid JSON.") from exc

    required = {"topic", "post", "hashtags", "illustration_brief"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise RuntimeError("Generated content is missing required fields.")

    # The code supplies the topic and source facts, rather than trusting model output.
    data["topic"] = topic
    data["source_facts"] = selected_topic["facts"]
    data["post"] = (
        str(data["post"])
        .replace("\u2014", ",")
        .replace("\u2013", "-")
        .strip()
    )
    data["illustration_brief"] = (
        str(data["illustration_brief"])
        .replace("\u2014", ",")
        .replace("\u2013", "-")
        .strip()
    )

    word_count = len(data["post"].split())
    if word_count < 45 or word_count > 110:
        raise RuntimeError(f"Post body must contain 45 to 110 words, received {word_count}.")
    if not data["illustration_brief"]:
        raise RuntimeError("Generated illustration brief is empty.")
    if not isinstance(data["hashtags"], list):
        raise RuntimeError("Generated hashtags must be a list.")

    data["hashtags"] = clean_hashtags(data["hashtags"])
    if len(data["hashtags"]) < 3:
        raise RuntimeError("At least three relevant hashtags are required.")

    OUTPUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Success: generated a {word_count}-word LinkedIn post.")
    print(f"Topic: {topic}")
    print(f"Saved to {OUTPUT_FILE}")
    print("\nPost preview:\n")
    print(data["post"])
    print("\nHashtags:", " ".join(f"#{tag}" for tag in data["hashtags"]))
    print("\nIllustration brief:\n")
    print(data["illustration_brief"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
