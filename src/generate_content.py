import json
import os
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

OUTPUT_FILE = Path("content.json")
PORTFOLIO_URL = "https://pandeynikhilone.github.io/"

# Source-grounded plan based on the resume and public GitHub repositories.
# The sequence starts on 2026-10-11 and cycles every 30 days.
TOPIC_PLAN = [
    {
        "topic": "My Techqueto internship: building charts in React",
        "facts": [
            "Resume: frontend developer intern at Techqueto Pvt Ltd. from December 2025 to January 2026.",
            "Worked with React, TypeScript, and Google Charts on line, bar, area, and pie charts.",
            "Chart data and configuration were JSON-driven rather than hardcoded.",
            "Created reusable chart utilities in common.ts.",
            "Worked with asynchronous loading using React useEffect.",
            "Debugged TypeScript, data-shape, and chart-rendering problems."
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

SLIDE_VISUAL_TYPES = {
    "chart", "flow", "code", "product", "database",
    "form", "checklist", "git", "stack", "learning",
}

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic": {"type": "STRING"},
        "post": {"type": "STRING"},
        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}},
        "video_title": {"type": "STRING"},
        "slides": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "body": {"type": "STRING"},
                    "visual_type": {"type": "STRING"},
                },
                "required": ["title", "body", "visual_type"],
            },
        },
    },
    "required": ["topic", "post", "hashtags", "video_title", "slides"],
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
    """Retry transient service failures without inventing fallback post content."""
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


def clean_text(value):
    return str(value).replace("\u2014", ",").replace("\u2013", "-").strip()


def clean_hashtags(values):
    result = []
    seen = set()
    for value in values:
        tag = "".join(
            char for char in str(value).strip().lstrip("#")
            if char.isalnum() or char == "_"
        )
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            result.append(tag)
    return result[:4]


def fallback_hashtags(topic):
    text = str(topic).casefold()
    if "techqueto" in text or "chart" in text or "react" in text:
        return ["ReactJS", "TypeScript", "FrontendDevelopment", "SoftwareDevelopment"]
    if "truloop" in text or "review" in text or "mongodb" in text:
        return ["NextJS", "FullStackDevelopment", "WebDevelopment", "MongoDB"]
    if "techfest" in text or "registration" in text or "student" in text:
        return ["JavaScript", "FrontendDevelopment", "WebDevelopment", "MCAStudent"]
    return ["SoftwareDevelopment", "LearningInPublic", "MCAStudent", "WebDevelopment"]


def source_grounded_fallback(topic):
    """Small, verified backup for today's Day 2 post if Gemini is unavailable."""
    if topic != "Replacing hardcoded chart values with JSON-driven data":
        raise RuntimeError("No deterministic fallback is defined for this topic.")
    return {
        "topic": topic,
        "post": (
            "One improvement from my Techqueto internship was moving chart data and configuration "
            "out of hardcoded frontend files.\n\n"
            "I worked with React, TypeScript, and Google Charts. Keeping values and chart settings "
            "in structured JSON made the display components cleaner and easier to adjust, instead "
            "of mixing data setup into rendering code.\n\n"
            "The lesson is simple: keeping data separate from presentation can make frontend "
            "components easier to maintain as requirements change. It was a useful reminder to keep "
            "configuration and rendering responsibilities distinct."
        ),
        "hashtags": ["ReactJS", "TypeScript", "GoogleCharts", "WebDevelopment"],
        "video_title": "From hardcoded chart values to JSON",
        "slides": [
            {
                "title": "Why hardcoded values hurt",
                "body": "Mixing chart values into frontend files can make components rigid.",
                "visual_type": "code",
            },
            {
                "title": "Move chart settings into JSON",
                "body": "Structured JSON keeps chart data and configuration separate from rendering.",
                "visual_type": "flow",
            },
            {
                "title": "Built with React and TypeScript",
                "body": "The internship work used React, TypeScript, and Google Charts.",
                "visual_type": "chart",
            },
            {
                "title": "Keep rendering logic cleaner",
                "body": "Separating settings from display makes adjustments easier to manage.",
                "visual_type": "stack",
            },
            {
                "title": "The practical takeaway",
                "body": "Separate data from presentation to make frontend code easier to maintain.",
                "visual_type": "learning",
            },
        ],
    }


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
Create one LinkedIn post plus exactly five short animated-video slide scripts.
Everything must be grounded in Nikhil Pandey's resume and public GitHub project details.

Today's topic: {topic}
Verified source facts:
{source_facts}

Topic angle: {post_angle}

LinkedIn text requirements:
- Aim for 70 to 95 words. Hard maximum: 110 words.
- Write like an MCA student or early-career developer describing real work in a direct, natural voice.
- Start with a clear, specific opening line. Use short paragraphs separated by blank lines. At most three short bullet points if useful.
- Finish with a concise takeaway. Avoid generic motivation, sales language, excessive excitement, engagement bait, and stock phrases.
- Do not invent personal stories, feelings, incidents, fixes, outcomes, users, metrics, dates, features, technical decisions, or achievements.
- Use first person only for contributions explicitly attributed to Nikhil. Credit collaborators accurately.
- Do not describe Truloop's receipt validation as guaranteed proof of purchase.
- Do not use long dash punctuation. Use ordinary punctuation and short sentences.
- Return 3 or 4 relevant hashtags separately from the post body.
- The post body is the LinkedIn caption accompanying the video, not text to place in a video footer.
- Make the caption clearly explain the specific work shown in today's video and why the implementation detail matters.
- Use 2 or 3 short paragraphs with blank lines. Keep the first line specific, not generic.
- The caption must make sense when read without watching the video. Do not leave it as just a title or a teaser.
- Keep the hashtags separate so the publisher can append them after the main body.

Video requirements:
- Give a short, accurate video title.
- Return exactly five slides, each with a short title, a body of 5 to 18 words, and one visual_type.
- Slide titles should generally be 3 to 7 words and readable on a phone.
- visual_type must be one of: chart, flow, code, product, database, form, checklist, git, stack, learning.
- Use a simple sequence: introduce the real problem or task, explain the implementation, show a key detail, add a practical implication, end with a grounded takeaway.
- Use only the verified facts above. Do not invent UI, product features, data, metrics, or outcomes.
- Slides will be rendered directly into a 4:5 animated MP4 with typography, diagrams, and locally drawn graphics. Do not request external artwork or stock footage. Select only a visual_type.
- Keep slide copy brief, high contrast, and mobile-readable.

Portfolio CTA instruction: {portfolio_cta_instruction}

Return only JSON with topic, post, hashtags, video_title, and slides.
"""

    print(f"Generating day {topic_index + 1}/{len(TOPIC_PLAN)} for {today.date()}: {topic}")
    print("Verified source facts:")
    print(source_facts)

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000),
    )
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    try:
        with client:
            response = generate_with_retry(client, model, prompt)
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        data = json.loads(response.text)
    except Exception as exc:
        if topic != "Replacing hardcoded chart values with JSON-driven data":
            raise
        print(
            "WARNING: Gemini generation failed for today's Day 2 topic "
            f"({type(exc).__name__}: {exc}). Using a verified, source-grounded fallback."
        )
        data = source_grounded_fallback(topic)

    required = {"topic", "post", "hashtags", "video_title", "slides"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise RuntimeError("Generated content is missing required fields.")

    data["topic"] = topic
    data["source_facts"] = selected_topic["facts"]
    data["post"] = clean_text(data["post"])
    data["video_title"] = clean_text(data["video_title"])[:180]

    word_count = len(data["post"].split())
    if word_count < 45 or word_count > 110:
        raise RuntimeError(f"Post body must contain 45 to 110 words, received {word_count}.")
    if not data["video_title"]:
        data["video_title"] = topic[:180]
    if not isinstance(data["hashtags"], list):
        raise RuntimeError("Generated hashtags must be a list.")
    data["hashtags"] = clean_hashtags(data["hashtags"] + fallback_hashtags(topic))
    if len(data["hashtags"]) < 3:
        raise RuntimeError("Could not prepare three relevant hashtags.")

    slides = data["slides"]
    if not isinstance(slides, list) or len(slides) != 5:
        raise RuntimeError("Exactly five video slides are required.")

    cleaned_slides = []
    for number, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise RuntimeError(f"Slide {number} is not a valid object.")
        title = clean_text(slide.get("title", ""))
        body = clean_text(slide.get("body", ""))
        visual_type = clean_text(slide.get("visual_type", "")).casefold()
        if not title or not body:
            raise RuntimeError(f"Slide {number} is missing its title or body.")
        if len(title.split()) > 9:
            raise RuntimeError(f"Slide {number} title is too long for mobile viewing.")
        body_words = len(body.split())
        if body_words < 4 or body_words > 20:
            raise RuntimeError(f"Slide {number} body must contain 4 to 20 words.")
        if visual_type not in SLIDE_VISUAL_TYPES:
            raise RuntimeError(f"Slide {number} uses unsupported visual_type: {visual_type}")
        cleaned_slides.append({"title": title, "body": body, "visual_type": visual_type})

    data["slides"] = cleaned_slides
    OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Success: generated {word_count}-word post and five video slides.")
    print(f"Topic: {topic}")
    print("\nPost preview:\n")
    print(data["post"])
    print("\nHashtags:", " ".join(f"#{tag}" for tag in data["hashtags"]))
    print("\nSlides:")
    for index, slide in enumerate(data["slides"], start=1):
        print(f"{index}. {slide['title']} [{slide['visual_type']}]")
        print(f"   {slide['body']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
