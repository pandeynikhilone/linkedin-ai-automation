import json
import os
import random
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

OUTPUT_FILE = Path("content.json")
LEDGER_FILE = Path("published-ledger.json")
PORTFOLIO_URL = "https://pandeynikhilone.github.io/"

# Source-grounded plan based on the resume and public GitHub repositories.
# The first topic was published on 2026-10-11. Scheduled progression follows the latest
# confirmed published plan topic in the ledger, then wraps after 30 topics.
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
        "topic": "Understanding what happens behind the TruLoop interface",
        "facts": [
            "The Next.js frontend lives in the frontend folder and the Express API lives in the backend folder.",
            "backend/src/app.js mounts separate /api/products and /api/reviews route modules.",
            "The product and review route modules call controller functions that read and update MongoDB documents through Mongoose models.",
            "After a review is created, backend/src/controllers/review.controller.js recalculates and saves the product averageRating and reviewCount."
        ],
        "angle": "Trace one request from the interface to an Express route, controller, and MongoDB operation, then back to the response. Describe the repository structure accurately and do not claim the whole request lifecycle was traced unless the code was actually inspected."
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


def _published_record_timestamp(record, ledger_key):
    """Return a comparable timestamp for ordering confirmed publications."""
    timestamp_text = (
        record.get("published_at")
        or record.get("started_at")
        or record.get("recorded_at")
    )
    try:
        timestamp = datetime.fromisoformat(str(timestamp_text).replace("Z", "+00:00")) if timestamp_text else None
    except (TypeError, ValueError):
        timestamp = None

    if timestamp is None:
        try:
            timestamp = datetime.fromisoformat(str(ledger_key)[:10])
        except (TypeError, ValueError):
            return float("-inf")

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return timestamp.timestamp()


def next_topic_index_from_ledger(dates):
    """Return the next plan index after the latest successfully published plan topic.

    Failed or uncertain records are deliberately ignored, so retries keep the same topic.
    Once Day 30 is published, the sequence wraps back to Day 1.
    """
    topic_indices = {
        entry["topic"]: index
        for index, entry in enumerate(TOPIC_PLAN)
    }
    latest_order = None
    latest_topic_index = None

    for ledger_key, record in dates.items():
        if not isinstance(record, dict) or record.get("status") != "published":
            continue

        topic_index = topic_indices.get(record.get("topic"))
        if topic_index is None:
            continue

        order = (_published_record_timestamp(record, ledger_key), str(ledger_key))
        if latest_order is None or order > latest_order:
            latest_order = order
            latest_topic_index = topic_index

    if latest_topic_index is None:
        return None
    return (latest_topic_index + 1) % len(TOPIC_PLAN)


def select_topic_index(today, requested_day=""):
    """Choose a forced manual day or the next unpublished day in sequence."""
    if requested_day:
        try:
            topic_day = int(requested_day)
        except ValueError as exc:
            raise RuntimeError("PUBLISH_TOPIC_DAY must be an integer from 1 to 30.") from exc
        if not 1 <= topic_day <= len(TOPIC_PLAN):
            raise RuntimeError(f"PUBLISH_TOPIC_DAY must be between 1 and {len(TOPIC_PLAN)}.")
        print(f"Using explicitly requested content-plan day {topic_day}.")
        return topic_day - 1

    if LEDGER_FILE.exists():
        try:
            ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Could not safely read published-ledger.json to select the next topic.") from exc
        if not isinstance(ledger, dict) or not isinstance(ledger.get("dates"), dict):
            raise RuntimeError("published-ledger.json has an unexpected structure; refusing to guess the next topic.")

        next_index = next_topic_index_from_ledger(ledger["dates"])
        if next_index is not None:
            previous_index = (next_index - 1) % len(TOPIC_PLAN)
            print(
                f"Continuing with Day {next_index + 1}/{len(TOPIC_PLAN)} after the latest "
                f"confirmed plan topic: {TOPIC_PLAN[previous_index]['topic']}."
            )
            return next_index

    elapsed_days = max(0, (today - PLAN_START_DATE).days)
    return elapsed_days % len(TOPIC_PLAN)


SLIDE_VISUAL_TYPES = {
    "chart", "flow", "code", "product", "database",
    "form", "checklist", "git", "stack", "learning", "website",
}
SLIDE_LAYOUTS = {"hero", "split", "evidence", "process", "editorial", "detail", "closing"}

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
                    "visual_type": {
                        "type": "STRING",
                        "enum": ["chart", "flow", "code", "product", "database", "form", "checklist", "git", "stack", "learning", "website"],
                    },
                    "layout": {
                        "type": "STRING",
                        "enum": ["hero", "split", "evidence", "process", "editorial", "detail", "closing"],
                    },
                    "visual_labels": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["title", "body", "visual_type", "layout", "visual_labels"],
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


def normalize_post_text(value):
    """Standardize all captions as three plain-text paragraphs."""
    text = clean_text(value)
    blocks = re.split(r"\n\s*\n", text)
    paragraphs = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if lines:
            paragraphs.append(" ".join(lines))
    return "\n\n".join(paragraphs)


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
    """Verified deterministic content for selected topics if Gemini is unavailable."""
    if topic == "Replacing hardcoded chart values with JSON-driven data":
        return {
            "topic": topic,
            "post": (
                "At Techqueto, chart data and configuration were moved from hardcoded values to JSON-driven values. "
                "The work used TypeScript, React, and Google Charts.\n\n"
                "Keeping configuration separate from component logic makes it easier to see which values drive a chart "
                "and which code renders it. It also gives the data a consistent place to be reviewed when a chart needs an update.\n\n"
                "I'm learning to treat data shape as part of the interface between code and visualization, not as an afterthought. "
                "The goal is clarity, not a claim of measured performance gains."
            ),
            "hashtags": ["ReactJS", "TypeScript", "GoogleCharts", "FrontendDevelopment"],
            "video_title": "Replacing Hardcoded Chart Values With JSON-Driven Data",
            "slides": [
                {
                    "title": "Move Chart Values Into Data",
                    "body": "The Techqueto chart work used JSON-driven values instead of hardcoded values.",
                    "visual_type": "chart",
                    "layout": "hero",
                    "visual_labels": ["JSON data", "Chart values", "Google Charts"],
                },
                {
                    "title": "Separate Configuration From Rendering",
                    "body": "Structured values describe chart data while React components render the visualization.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["JSON configuration", "React component", "Rendered chart"],
                },
                {
                    "title": "Keep The Data Path Clear",
                    "body": "A consistent configuration makes the values driving a chart easier to review.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["TypeScript", "Data shape", "Chart options"],
                },
                {
                    "title": "Use The Tools In Context",
                    "body": "The documented stack for this work included TypeScript, React, and Google Charts.",
                    "visual_type": "stack",
                    "layout": "split",
                    "visual_labels": ["TypeScript", "React", "Google Charts"],
                },
                {
                    "title": "Prefer Clarity Over Big Claims",
                    "body": "The implementation choice is documented; no quantified performance gain is claimed.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Clear configuration", "Readable code", "Measured claims only"],
                },
            ],
        }

    if topic == "Checking purchase dates against product release dates":
        return {
            "topic": topic,
            "post": (
                "TruLoop checks the relationship between a purchase date and a product's release date. "
                "When both dates are present, the review controller rejects a purchase date earlier than the release date.\n\n"
                "Each date might look valid alone while the pair is inconsistent. Comparing related fields lets the application apply a clear rule before a review is created.\n\n"
                "This is a consistency check, not proof that a purchase happened or a guarantee against fake reviews. "
                "I want to describe the code accurately without overstating its effect."
            ),
            "hashtags": ["FullStackDevelopment", "WebDevelopment", "SoftwareDevelopment", "MCAStudent"],
            "video_title": "Checking Purchase Dates Against Release Dates",
            "slides": [
                {
                    "title": "Compare Related Dates",
                    "body": "The rule checks purchase and release dates when both are present.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Live TruLoop UI", "TruLoop project", "Interface context"],
                },
                {
                    "title": "Check The Date Order",
                    "body": "A purchase date earlier than the release date is rejected.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["Purchase date", "Compare", "Release date"],
                },
                {
                    "title": "Reject Inconsistent Data",
                    "body": "The review controller applies the rule before creating the review.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["Review controller", "Date check", "Validation result"],
                },
                {
                    "title": "Keep The Claim Narrow",
                    "body": "This check does not prove that a purchase actually happened.",
                    "visual_type": "learning",
                    "layout": "split",
                    "visual_labels": ["Consistency check", "Not proof", "Limited scope"],
                },
                {
                    "title": "Validate With Context",
                    "body": "Related fields can be valid alone but inconsistent together.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Related values", "Clear rule", "Careful claims"],
                },
            ],
        }

    if topic == "Validating the data required to submit a Truloop review":
        return {
            "topic": topic,
            "post": (
                "Review forms need clear requirements before a submission can be created.\n\n"
                "In TruLoop, the review controller requires productId, rating, comment, reviewer, usageDuration, and recommend before creating a review. "
                "Naming these fields makes the endpoint's expected input clear and describes what a complete review request must contain.\n\n"
                "I'm learning to treat validation as part of an API contract, not just a frontend convenience. "
                "The backend should check the data it receives, even when the interface already asks users for the same values."
            ),
            "hashtags": ["FullStackDevelopment", "BackendDevelopment", "WebDevelopment", "MCAStudent"],
            "video_title": "Validating the Data Required to Submit a TruLoop Review",
            "slides": [
                {
                    "title": "Required Fields Matter",
                    "body": "The live TruLoop review interface shows where a review request begins.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Review form", "Required inputs", "Submit review"],
                },
                {
                    "title": "Validate The Request",
                    "body": "The controller checks the fields required for a review.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["productId", "rating", "comment", "reviewer", "usageDuration", "recommend"],
                },
                {
                    "title": "Make The Contract Clear",
                    "body": "Required fields define what the review endpoint expects.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["Request body", "Validation", "Review creation"],
                },
                {
                    "title": "Frontend And Backend",
                    "body": "The server still checks submitted data, even when the interface asks for it.",
                    "visual_type": "learning",
                    "layout": "split",
                    "visual_labels": ["Frontend form", "API request", "Backend validation"],
                },
                {
                    "title": "Validate Before Creating",
                    "body": "Clear requirements make endpoint behavior easier to understand.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Clear inputs", "Consistent checks", "Review record"],
                },
            ],
        }

    if topic == "Organizing Truloop's routes by responsibility":
        return {
            "topic": topic,
            "post": (
                "Clear routes give each feature a place to start. I'm reviewing how TruLoop groups its frontend pages and backend API paths.\n\n"
                "Frontend routes cover products, product information, product reviews, review submission, profiles, and authentication. Backend route files separate auth, products, reviews, uploads, and admin. This makes the right area easier to locate before tracing its behavior.\n\n"
                "As an MCA student, I'm learning to follow both sides of a full-stack application instead of treating each URL in isolation. A clear route structure gives me a useful starting point when reading or debugging code."
            ),
            "hashtags": ["NextJS", "NodeJS", "WebDevelopment", "MCAStudent"],
            "video_title": "Organizing TruLoop Routes by Responsibility",
            "slides": [
                {
                    "title": "Clear Routes Make Features Easier",
                    "body": "TruLoop separates page paths for distinct product and account features.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Frontend pages", "Feature routes", "Live TruLoop website"],
                },
                {
                    "title": "Group Frontend Pages By Feature",
                    "body": "Products, product information, reviews, profiles, and authentication have separate routes.",
                    "visual_type": "flow",
                    "layout": "split",
                    "visual_labels": ["Products", "Reviews", "Authentication"],
                },
                {
                    "title": "Keep Backend Routes Organized",
                    "body": "Separate files cover auth, products, reviews, uploads, and admin.",
                    "visual_type": "code",
                    "layout": "process",
                    "visual_labels": ["Auth routes", "Product routes", "Review routes"],
                },
                {
                    "title": "Trace Each Route With Purpose",
                    "body": "Clear route ownership helps me find where a feature starts.",
                    "visual_type": "stack",
                    "layout": "editorial",
                    "visual_labels": ["Route file", "Controller", "Feature behavior"],
                },
                {
                    "title": "Start With One Clear Responsibility",
                    "body": "I am learning to follow routes before debugging a full-stack feature.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Find the route", "Trace the feature", "Understand the flow"],
                },
            ],
        }

    if topic == "Keeping product ratings current after a new review":
        return {
            "topic": topic,
            "post": (
                "A new review is only one part of keeping product information current. The controller's follow-up work matters too.\n\n"
                "In TruLoop, the review controller retrieves the product's reviews, calculates the average rating, updates averageRating and reviewCount, and saves the product after a review is created.\n\n"
                "I'm learning to trace what happens after a write operation instead of stopping at the successful request. Following the calculation and save makes the data flow easier to understand and debug."
            ),
            "hashtags": ["FullStackDevelopment", "MongoDB", "WebDevelopment", "MCAStudent"],
            "video_title": "Keeping Product Ratings Current After a New Review",
            "slides": [
                {
                    "title": "Keep Product Ratings Current",
                    "body": "The live TruLoop interface presents product ratings alongside review information.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Product rating", "Review summary", "TruLoop interface"],
                },
                {
                    "title": "Recalculate After A Review",
                    "body": "The controller retrieves reviews for the product after creation.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["Review controller", "Product reviews", "New review"],
                },
                {
                    "title": "Update The Product Summary",
                    "body": "It calculates averageRating and reviewCount, then saves the product.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["Retrieve reviews", "Calculate aggregates", "Save product"],
                },
                {
                    "title": "Store The Updated Aggregates",
                    "body": "The product is saved with the calculated rating and review count.",
                    "visual_type": "database",
                    "layout": "editorial",
                    "visual_labels": ["averageRating", "reviewCount", "Saved product"],
                },
                {
                    "title": "Trace The Update Path",
                    "body": "Follow review creation through calculation and product save.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["New review", "Updated aggregates", "Product saved"],
                },
            ],
        }

    if topic == "Reusable navigation, product cards, and review sections":
        return {
            "topic": topic,
            "post": (
                "Reusable components become valuable when several parts of a page need a consistent structure.\n\n"
                "In TruLoop, I built reusable UI components for navigation menus, product cards, and review sections. "
                "Shared components keep repeated interface patterns together and make those sections easier to update without duplicating their structure.\n\n"
                "My focus is finding the right level of reuse: consistent where sections are similar, but still clear enough to change each component deliberately. "
                "That makes component structure a practical part of maintainable frontend work."
            ),
            "hashtags": ["NextJS", "ReactJS", "FrontendDevelopment", "WebDevelopment"],
            "video_title": "Reusable Navigation, Product Cards, and Review Sections",
            "slides": [
                {
                    "title": "Reusable UI Starts With Structure",
                    "body": "The real interface shows how navigation, products, and reviews meet on one page.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Live TruLoop UI", "Navigation", "Product browsing"],
                },
                {
                    "title": "Share Patterns Across Page Sections",
                    "body": "Reusable menus, product cards, and review sections keep repeated UI patterns manageable.",
                    "visual_type": "product",
                    "layout": "split",
                    "visual_labels": ["Navigation menus", "Product cards", "Review sections"],
                },
                {
                    "title": "Choose A Useful Reuse Boundary",
                    "body": "Shared components support consistency, but each component still needs a clear responsibility.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["Shared component", "Page section", "Component responsibility"],
                },
                {
                    "title": "Keep The Component Easy To Change",
                    "body": "Clear inputs and responsibilities make future updates easier to follow.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["Component structure", "Props and content", "Rendered UI"],
                },
                {
                    "title": "Maintainability Starts With Clear Components",
                    "body": "The goal is easier changes, not abstraction for its own sake.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Consistent UI", "Readable code", "Maintainability"],
                },
            ],
        }

    if topic == "Understanding what happens behind the TruLoop interface":
        return {
            "topic": topic,
            "post": (
                "One thing I wanted to understand in TruLoop is what happens after someone opens a product or submits a review.\n\n"
                "The frontend uses Next.js and React, while Express exposes separate product and review routes. Controllers use Mongoose models to read or update MongoDB documents, and the review controller recalculates averageRating and reviewCount after a new review.\n\n"
                "I am using this project to trace that request path end to end instead of treating the interface and database as separate pieces. Understanding the flow should help me debug and improve it more deliberately."
            ),
            "hashtags": ["NextJS", "FullStackDevelopment", "WebDevelopment", "MongoDB"],
            "video_title": "What Happens Behind the TruLoop Interface",
            "slides": [
                {
                    "title": "What Happens Behind TruLoop",
                    "body": "The page is only the visible part of a full stack request.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Live TruLoop UI", "Frontend"],
                },
                {
                    "title": "Follow The Request Path",
                    "body": "The frontend sends a request to an Express product or review route.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["Next.js frontend", "Express route", "Controller", "MongoDB"],
                },
                {
                    "title": "Controllers Handle The Logic",
                    "body": "Controllers call Mongoose models to read and update MongoDB documents.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["Review controller", "Mongoose model", "Database operation"],
                },
                {
                    "title": "Ratings Update After Reviews",
                    "body": "After a review, the controller updates averageRating and reviewCount on the product.",
                    "visual_type": "database",
                    "layout": "editorial",
                    "visual_labels": ["New review", "averageRating", "reviewCount"],
                },
                {
                    "title": "Trace It Before Improving",
                    "body": "Tracing each step gives me a clearer starting point when debugging changes.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Request", "Controller", "Database", "Response"],
                },
            ],
        }

    if topic == "Designing a product browsing and review flow":
        return {
            "topic": topic,
            "post": (
                "A product page needs to do more than display a name and a picture. People also need enough context to judge whether an item fits what they are looking for.\n\n"
                "TruLoop brings a growing product catalog together with product specifications, in depth user reviews, and the option to submit a review. That connects browsing with a way to learn from other people's experiences.\n\n"
                "I am thinking about how each section can support the next step without overwhelming the page. Clear information structure matters because useful reviews only help when people can find and understand them."
            ),
            "hashtags": ["FullStackDevelopment", "WebDevelopment", "ProductExperience", "MCAStudent"],
            "video_title": "Designing a Product Browsing and Review Flow",
            "slides": [
                {
                    "title": "Browse Products With Context",
                    "body": "A catalog gives people a starting point for comparing available products.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["Live TruLoop UI", "Product catalog", "Browse products"],
                },
                {
                    "title": "Check Product Details First",
                    "body": "Specifications add context beyond a product name and image.",
                    "visual_type": "product",
                    "layout": "split",
                    "visual_labels": ["Product details", "Specifications", "Catalog"],
                },
                {
                    "title": "Reviews Add Useful Context",
                    "body": "In depth user reviews help readers consider experiences beyond listed specifications.",
                    "visual_type": "flow",
                    "layout": "evidence",
                    "visual_labels": ["Specifications", "User reviews", "Product context"],
                },
                {
                    "title": "Make Review Submission Clear",
                    "body": "The project also gives users a way to submit their own reviews.",
                    "visual_type": "form",
                    "layout": "process",
                    "visual_labels": ["Review form", "User submission", "Product review"],
                },
                {
                    "title": "Connect Each Step Naturally",
                    "body": "Clear information structure helps people find and understand useful product reviews.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Browse", "Compare", "Read reviews", "Submit review"],
                },
            ],
        }

    if topic == "Separating Truloop's frontend and backend":
        return {
            "topic": topic,
            "post": (
                "Keeping frontend and backend folders separate makes a project easier to navigate.\n\n"
                "In TruLoop, the frontend uses Next.js and the backend uses Express. The repository keeps them in separate frontend and backend folders, and the root README explains how to run them together or separately. Separate folders describe code organization; they do not automatically make an application a microservices system.\n\n"
                "My takeaway is to document the folder structure and startup steps clearly. A useful setup guide helps another developer explore the interface and API without guessing how the parts fit together."
            ),
            "hashtags": ["NextJS", "ExpressJS", "FullStackDevelopment", "WebDevelopment"],
            "video_title": "Separating TruLoop's Frontend and Backend",
            "slides": [
                {
                    "title": "Two Parts Of One Project",
                    "body": "TruLoop keeps its Next.js frontend and Express backend in separate folders.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["TruLoop interface", "Next.js frontend", "Project structure"],
                },
                {
                    "title": "Keep Each Side Organized",
                    "body": "The frontend and backend folders make each part easier to locate in the repository.",
                    "visual_type": "stack",
                    "layout": "split",
                    "visual_labels": ["frontend folder", "backend folder", "Next.js", "Express"],
                },
                {
                    "title": "Understand How They Run",
                    "body": "The root README explains how to run both parts together or separately.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["Read setup guide", "Start frontend", "Start backend"],
                },
                {
                    "title": "Structure Is Not Microservices",
                    "body": "Separate folders describe code organization, not a claim about distributed services.",
                    "visual_type": "code",
                    "layout": "detail",
                    "visual_labels": ["Repository folders", "Application structure", "Accurate terminology"],
                },
                {
                    "title": "Document The Setup Clearly",
                    "body": "Clear startup instructions help another developer understand how the parts fit together.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Readable README", "Repeatable setup", "Developer onboarding"],
                },
            ],
        }

    if topic == "Connecting Truloop's interface to backend APIs":
        return {
            "topic": topic,
            "post": (
                "A frontend feature is only one part of a full-stack request. The interface needs an API to read or update data.\n\n"
                "In TruLoop, I worked with Node.js and Express.js APIs for products, reviews, and user interactions. "
                "Thinking through the request path helps separate the interface from backend handling, then connect both through a clear response. "
                "I am keeping the explanation grounded in the documented project instead of assuming deployment details or performance results.\n\n"
                "When debugging a full-stack feature, what do you check first: the browser request, the Express route, or the data operation?"
            ),
            "hashtags": ["ExpressJS", "NodeJS", "FullStackDevelopment", "WebDevelopment"],
            "video_title": "Connecting TruLoop's Frontend to Backend APIs",
            "slides": [
                {
                    "title": "Follow a Frontend Request",
                    "body": "The visible interface is one part of a request that needs backend data.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["TruLoop interface", "Frontend", "API request"],
                },
                {
                    "title": "Frontend Presents the Data",
                    "body": "The interface organizes user actions and presents product and review information.",
                    "visual_type": "stack",
                    "layout": "split",
                    "visual_labels": ["Frontend", "Product view", "Review view"],
                },
                {
                    "title": "Express Handles API Requests",
                    "body": "Node.js and Express.js APIs support products, reviews, and user interactions.",
                    "visual_type": "flow",
                    "layout": "process",
                    "visual_labels": ["API request", "Express backend", "Response"],
                },
                {
                    "title": "Trace the Data Operation",
                    "body": "Check the route logic and data operation before assuming where a problem starts.",
                    "visual_type": "database",
                    "layout": "detail",
                    "visual_labels": ["Route logic", "Data operation", "Returned data"],
                },
                {
                    "title": "Debug One Layer at a Time",
                    "body": "A clear request path gives me a more deliberate starting point for debugging.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Browser request", "Backend route", "Data operation"],
                },
            ],
        }

    if topic == "A look at Truloop's receipt proof validation":
        return {
            "topic": topic,
            "post": (
                "Receipt proof validation is an interesting example of a practical check that still has limits.\n\n"
                "In TruLoop, the service uses Tesseract.js to read text from image files and pdf-parse for PDFs. "
                "It then checks the extracted text for receipt-related terms and a match with the product name.\n\n"
                "That is a text-based validation step, not proof that a purchase is genuine. "
                "I want to keep that distinction clear when building trust features: useful checks can reduce ambiguity without promising certainty."
            ),
            "hashtags": ["FullStackDevelopment", "WebDevelopment", "SoftwareDevelopment", "MCAStudent"],
            "video_title": "How TruLoop Checks Receipt Proof",
            "slides": [
                {
                    "title": "Receipt Proof Validation Starts With Text",
                    "body": "The interface introduces a check, but text extraction is only one step.",
                    "visual_type": "website",
                    "layout": "hero",
                    "visual_labels": ["TruLoop review flow", "Receipt proof", "Validation step"],
                },
                {
                    "title": "Extract Text From Each File Type",
                    "body": "Tesseract.js handles image OCR, while pdf-parse extracts text from PDFs.",
                    "visual_type": "flow",
                    "layout": "split",
                    "visual_labels": ["Image file", "Tesseract.js OCR", "PDF file", "pdf-parse"],
                },
                {
                    "title": "Look For Receipt Terms And Product Name",
                    "body": "The validator checks extracted text for receipt terms and a product-name match.",
                    "visual_type": "checklist",
                    "layout": "process",
                    "visual_labels": ["Extracted text", "Receipt-related terms", "Product name"],
                },
                {
                    "title": "A Match Is Not Proof Of Purchase",
                    "body": "Text checks do not independently prove that a purchase was genuine.",
                    "visual_type": "checklist",
                    "layout": "detail",
                    "visual_labels": ["Text match", "Validation signal", "Not a guarantee"],
                },
                {
                    "title": "Be Clear About Validation Limits",
                    "body": "Trust features should explain what their checks can and cannot confirm.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Useful checks", "Clear limits", "Honest product claims"],
                },
            ],
        }

    if topic == "What Truloop means by real usage experience":
        return {
            "topic": topic,
            "post": (
                "TruLoop's README says product reviews should reflect real usage experience, not just a quick impression. "
                "It gives battery life and software stability as examples of details that matter when describing a product.\n\n"
                "That framing makes me think about review quality as more than a star rating. A useful review explains "
                "what someone actually observed, while the project aims to emphasize honest, unbiased feedback.\n\n"
                "I'm learning how clear examples can give readers context without suggesting that one review proves every claim. "
                "Specific observations help people understand what a reviewer means."
            ),
            "hashtags": ["NextJS", "FullStackDevelopment", "WebDevelopment", "MCAStudent"],
            "video_title": "What Real Usage Experience Adds To Reviews",
            "slides": [
                {
                    "title": "Real Usage Shapes Better Reviews",
                    "body": "TruLoop's README centers reviews on real product experience.",
                    "visual_type": "learning",
                    "layout": "hero",
                    "visual_labels": ["Real usage", "Review context", "Product experience"],
                },
                {
                    "title": "Look Beyond A Star Rating",
                    "body": "Battery life and software stability are README examples.",
                    "visual_type": "checklist",
                    "layout": "process",
                    "visual_labels": ["Battery life", "Software stability", "Observed experience"],
                },
                {
                    "title": "Describe What You Observed",
                    "body": "Specific observations give readers more context than a score alone.",
                    "visual_type": "form",
                    "layout": "detail",
                    "visual_labels": ["Observation", "Product context", "Review detail"],
                },
                {
                    "title": "Honest Feedback Needs Context",
                    "body": "The project aims to emphasize honest, unbiased product reviews.",
                    "visual_type": "product",
                    "layout": "split",
                    "visual_labels": ["Honest feedback", "Unbiased reviews", "Reader context"],
                },
                {
                    "title": "Keep Claims Within The Evidence",
                    "body": "A review describes experience; it does not prove every claim.",
                    "visual_type": "learning",
                    "layout": "closing",
                    "visual_labels": ["Clear evidence", "Careful claims", "Useful context"],
                },
            ],
        }

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
    today = datetime.now(ZoneInfo("Asia/Kolkata"))
    requested_day = os.getenv("PUBLISH_TOPIC_DAY", "").strip()
    custom_topic = os.getenv("PUBLISH_CUSTOM_TOPIC", "").strip().lower()
    custom_binary_search = custom_topic == "binary-search-cpp"
    custom_java_polymorphism = custom_topic == "java-polymorphism"
    if custom_topic and not (custom_binary_search or custom_java_polymorphism):
        raise RuntimeError("Unsupported custom topic key.")
    if custom_binary_search:
        topic_index = -1
        selected_topic = {
            "topic": "Binary Search in C++: Iterative and Recursive",
            "facts": [
                "Binary search requires a sorted array or range.",
                "Each comparison with the midpoint discards about half of the remaining search space.",
                "Iterative binary search uses a loop; recursive binary search calls itself on a smaller range.",
                "Both approaches take O(log n) time; iterative uses O(1) auxiliary space and recursive uses O(log n) call-stack space.",
                "Using low + (high - low) / 2 avoids the potential overflow of (low + high) / 2."
            ],
            "angle": "Teach binary search accurately with C++ examples, contrasting iterative and recursive methods."
        }
    elif custom_java_polymorphism:
        topic_index = -2
        selected_topic = {
            "topic": "Java Polymorphism: Reference Type vs Runtime Object",
            "facts": [
                "A parent-class reference in Java can refer to an instance of a child class.",
                "For an overridden instance method, dynamic dispatch selects the implementation from the actual object's class.",
                "Compile-time member access is checked against the declared reference type.",
                "Inheritance, overriding, and polymorphism are part of the user's current Core Java coursework."
            ],
            "angle": "Explain the difference between a variable's declared reference type and its runtime object's class using a small Java example. Write as a student practising Core Java, invite readers to share what helped polymorphism click, and do not imply professional Java project experience."
        }
    else:
        topic_index = select_topic_index(today.date(), requested_day)
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

    is_truloop_topic = topic_index in range(7, 21)
    website_visual_instruction = (
        "For this TruLoop topic, make exactly one slide use visual_type 'website' to show the genuine deployed interface. Use product, flow, form, code, or database visuals for the remaining explanation."
        if is_truloop_topic
        else "Do not use visual_type 'website' for this topic. Use a relevant diagram or code visual instead."
    )

    prompt = f"""
Create one LinkedIn post and exactly five short animated-video slide scripts.
Everything must be grounded in Nikhil Pandey's actual resume and public GitHub project details.

Today's topic: {topic}
Verified source facts:
{source_facts}

Topic angle: {post_angle}

The purpose of this account is to build a credible early-career developer profile. The audience includes other students, developers, and potential internship or job contacts. Posts should document real work and learning, not pretend to be an industry expert.

LinkedIn text requirements:
- For standard scheduled topics, write 70 to 95 words in exactly three plain-text paragraphs separated by one blank line. Only for the explicitly requested custom Binary Search or Java Polymorphism posts, write 95 to 110 words.
- Open with a specific observation, technical question, tradeoff, or problem tied to this topic. Do not use a standalone title.
- In the middle paragraph, explain the real implementation or code detail, using first person only where Nikhil's own contribution is documented.
- End with a practical lesson or something Nikhil is trying to understand more deeply. Do not force a call to action or a question into every post.
- Sound like a thoughtful MCA student explaining something he genuinely built or is learning. Use natural, straightforward wording, not corporate marketing copy or generic motivational writing.
- Vary the opening and sentence structure between topics. Avoid recurring formulas such as 'One thing I am learning', 'I have been working on', 'Excited to share', and 'Building this taught me' as automatic openers.
- Use no emojis, headings, bullets, numbered lists, markdown, or inline hashtags in the caption.
- Do not use em dashes or en dashes. Avoid unnecessary hyphenated phrases when a simpler wording works.
- Do not invent personal stories, feelings, incidents, bugs, fixes, results, users, metrics, dates, features, technical decisions, or achievements.
- Credit collaborators accurately. Do not describe TruLoop receipt text checks as proof that a purchase is genuine.
- Return 3 or 4 relevant hashtags separately from the body. The publisher appends them on their own line.
- The caption must stand on its own and explain why the specific technical detail matters. Do not write a teaser that depends on watching the video.

Video requirements:
- Give a short, accurate video title.
- Return exactly five slides: context, implementation, a key detail, how it applies in the project, and a practical takeaway.
- Each slide needs a title of 3 to 7 words, body copy of 5 to 18 words, one visual_type, one layout, and 2 to 4 short visual_labels.
- visual_type must be one of: chart, flow, code, product, database, form, checklist, git, stack, learning, website.
- layout must be one of: hero, split, evidence, process, editorial, detail, closing.
- Use five distinct layouts in the same video. The first must be hero and the last must be closing. Do not repeat one composition with only changed words or colours.
- visual_labels should identify the actual concepts shown, such as "Browser", "Express route", "Controller", and "MongoDB". Every label must be grounded in the verified facts, with no invented numbers or outcomes.
- Choose visuals according to the point being taught. Use a real request flow for architecture, meaningful data relationships for database topics, a genuine screenshot for the actual UI, and implementation evidence for code topics.
- {website_visual_instruction} Never redraw or fabricate the deployed interface. The website slide must use a genuine capture, and remaining slides should explain the relevant product flow, code, or architecture.
- Vary both composition and visual treatment across different topics while maintaining a coherent developer series. Avoid repeatedly using the same generic illustration, card arrangement, device mockup, or decorative filler.
- The "website" visual must use a screenshot captured from the live TruLoop website. If a genuine screenshot is unavailable, use a technical diagram instead.
- Use only verified facts above. Do not invent UI, product features, data, metrics, reviews, or outcomes.
- Slides are rendered into a 4:5 animated MP4 with typography, diagrams, and locally drawn graphics. Do not request external artwork or stock footage.
- Keep text short, high contrast, and readable on a phone. Visual labels must explain the diagram, not merely decorate it.

Portfolio CTA instruction: {portfolio_cta_instruction}

Return only JSON with topic, post, hashtags, video_title, and slides.
"""

    print(f"Generating day {topic_index + 1}/{len(TOPIC_PLAN)} for {today.date()}: {topic}")
    print("Verified source facts:")
    print(source_facts)

    fixed_day4_correction = os.getenv("PUBLISH_FIXED_DAY4_TEMPLATE", "").strip().lower() in {"1", "true", "yes"}
    fixed_day5_standard = os.getenv("PUBLISH_FIXED_DAY5_TEMPLATE", "").strip().lower() in {"1", "true", "yes"}
    fixed_day6_standard = os.getenv("PUBLISH_FIXED_DAY6_TEMPLATE", "").strip().lower() in {"1", "true", "yes"}
    if custom_binary_search:
        data = {
            "topic": topic,
            "post": (
                "Binary search is not just “check the middle.” It requires sorted data: each comparison proves one half cannot contain the target.\n\n"
                "For [1, 3, 5, 7, 9, 11, 13], searching for 9 checks 7 at index 3, so low becomes 4. Next, midpoint 11 makes high become 4. Midpoint 9 then finds the target at index 4. The condition low <= high keeps a one-element range searchable; low > high means the target is absent.\n\n"
                "Both versions take O(log n) time. Iteration uses O(1) auxiliary space; recursion uses O(log n) stack space. The midpoint formula low + (high - low) / 2 avoids potential addition overflow."
            ),
            "hashtags": ["DSA", "CPP", "BinarySearch", "ProblemSolving"],
            "video_title": "Binary Search in C++: Iterative vs Recursive",
            "slides": [
                {"title": "Binary Search Needs Sorted Data", "body": "Sorted order makes it safe to discard the half that cannot contain the target.", "visual_type": "learning", "layout": "hero", "visual_labels": ["1 3 5 7 9 11 13", "target = 9", "sorted ascending"]},
                {"title": "Trace Every Boundary Update", "body": "Target 9: midpoint 7 moves low right; midpoint 11 moves high left; midpoint 9 matches.", "visual_type": "code", "layout": "process", "visual_labels": ["Worked trace", "Target = 9"], "code_lines": ["a = [1, 3, 5, 7, 9, 11, 13]", "low = 0, high = 6", "mid = 3 -> a[3] = 7; low = 4", "mid = 5 -> a[5] = 11; high = 4", "mid = 4 -> a[4] = 9; found at index 4"]},
                {"title": "Iterative Binary Search in C++", "body": "The loop continues while low <= high, including the final one-element search range.", "visual_type": "code", "layout": "detail", "visual_labels": ["C++ implementation", "Loop invariant"], "code_lines": ["int binarySearch(const vector<int>& a, int x) {", "  int low = 0, high = (int)a.size() - 1;", "  while (low <= high) {", "    int mid = low + (high - low) / 2;", "    if (a[mid] == x) return mid;", "    if (a[mid] < x) low = mid + 1;", "    else high = mid - 1;", "  }", "  return -1;", "}"]},
                {"title": "Recursive Version and Base Case", "body": "The empty-range base case prevents invalid access; each call strictly reduces the interval.", "visual_type": "code", "layout": "editorial", "visual_labels": ["Recursive implementation", "Base case"], "code_lines": ["int binarySearch(const vector<int>& a, int x, int l, int r) {", "  if (l > r) return -1;", "  int m = l + (r - l) / 2;", "  if (a[m] == x) return m;", "  if (a[m] < x)", "    return binarySearch(a, x, m + 1, r);", "  return binarySearch(a, x, l, m - 1);", "}"]},
                {"title": "Complexity and Interview Details", "body": "Both are O(log n) time; iteration uses O(1) extra space, recursion O(log n) stack.", "visual_type": "learning", "layout": "closing", "visual_labels": ["Sorted input required", "O(log n) time", "O(1) iterative space", "O(log n) recursive stack"]}
            ]
        }
        print("Using deterministic C++ binary-search educational content.")
    elif custom_java_polymorphism:
        data = {
            "topic": topic,
            "post": (
                "Polymorphism clicked for me when I separated two questions: what type is the reference, and what object does it point to?\n\n"
                "In Java, Animal animal = new Dog() is a parent-type reference holding a child object. If Dog overrides an instance method such as sound(), calling animal.sound() runs the Dog implementation at runtime. But which members you can access are still checked against the declared reference type at compile time.\n\n"
                "I am practising OOP in Core Java, and tracing those two types separately helps me reason about the output. What made polymorphism click for you: a small code example, a diagram, or a project?"
            ),
            "hashtags": ["Java", "OOP", "MCA", "SoftwareDevelopment"],
            "video_title": "Java Polymorphism: Reference vs Runtime Object",
            "slides": [
                {"title": "One Reference, One Child Object", "body": "A parent type can refer to an object created from a child class.", "visual_type": "learning", "layout": "hero", "visual_labels": ["Animal reference", "Dog instance", "Java"]},
                {"title": "Compile Time Uses Reference Type", "body": "Available members are checked against the declared reference type.", "visual_type": "code", "layout": "split", "visual_labels": ["Declared type", "Member access"], "code_lines": ["Animal animal = new Dog();", "animal.sound();", "// Animal declares sound()"]},
                {"title": "Runtime Chooses Overridden Method", "body": "For an overridden instance method, the actual object's class determines the implementation.", "visual_type": "code", "layout": "process", "visual_labels": ["Method overriding", "Runtime dispatch"], "code_lines": ["class Dog extends Animal {", "  @Override", "  void sound() { System.out.println(\"Bark\"); }", "}"]},
                {"title": "Trace Both Types Separately", "body": "Ask what the variable is declared as and what object it holds.", "visual_type": "flow", "layout": "detail", "visual_labels": ["Declared type: Animal", "Runtime object: Dog", "Method dispatch"]},
                {"title": "What Made It Click?", "body": "A tiny runnable example can make dynamic method dispatch easier to see.", "visual_type": "learning", "layout": "closing", "visual_labels": ["Predict the output", "Run and compare", "Explain why"]}
            ]
        }
        print("Using deterministic Java polymorphism educational content.")
    elif fixed_day4_correction:
        if topic != "Loading chart data asynchronously with useEffect":
            raise RuntimeError("The fixed correction template is only available for Day 4.")
        data = {
            "topic": topic,
            "post": (
                "Loading chart data asynchronously is an important part of building data-driven React components.\n\n"
                "During my Techqueto internship, I worked with asynchronous data loading using React's useEffect in chart-related work. "
                "It reinforced the importance of organizing side effects within the component lifecycle instead of mixing data-loading logic "
                "into the chart's display code.\n\n"
                "My takeaway is simple: keeping data loading separate from rendering makes components easier to understand and maintain "
                "as a project evolves."
            ),
            "hashtags": ["ReactJS", "TypeScript", "FrontendDevelopment", "WebDevelopment"],
            "video_title": "Loading Chart Data with React useEffect",
            "slides": [
                {
                    "title": "Loading data in React",
                    "body": "Chart data may arrive after the component first renders.",
                    "visual_type": "flow",
                },
                {
                    "title": "Organize side effects",
                    "body": "React useEffect helps organize side-effect logic around component lifecycle changes.",
                    "visual_type": "code",
                },
                {
                    "title": "Keep data flow clear",
                    "body": "Separate asynchronous loading logic from the code that displays chart data.",
                    "visual_type": "flow",
                },
                {
                    "title": "Apply it to chart work",
                    "body": "This was part of my React chart development work at Techqueto.",
                    "visual_type": "chart",
                },
                {
                    "title": "A maintainable component",
                    "body": "Clear responsibilities make components easier to understand and maintain.",
                    "visual_type": "learning",
                },
            ],
        }
        print("Using the standardized, source-grounded Day 4 correction copy and slides.")
    elif fixed_day5_standard:
        if topic != "Debugging TypeScript and chart rendering issues":
            raise RuntimeError("The fixed standard template is only available for Day 5.")
        data = {
            "topic": topic,
            "post": (
                "Debugging chart issues requires more than looking at the final visual. "
                "TypeScript errors and unexpected data shapes can affect what a chart receives and displays.\n\n"
                "During my Techqueto internship, I worked on TypeScript, data-shape, and chart-rendering issues across multiple chart types. "
                "Checking the code, incoming values, and displayed result helps keep the investigation focused.\n\n"
                "My takeaway is to verify the types, data structure, and rendered output before changing the component. "
                "Looking at each layer makes it easier to identify where a mismatch may begin."
            ),
            "hashtags": ["TypeScript", "ReactJS", "GoogleCharts", "FrontendDevelopment"],
            "video_title": "Debugging Chart Issues Step by Step",
            "slides": [
                {
                    "title": "Start With The Actual Issue",
                    "body": "Chart display problems can involve TypeScript, data shape, or rendering.",
                    "visual_type": "flow",
                },
                {
                    "title": "Check The Expected Types",
                    "body": "TypeScript helps identify whether values fit the expectations of the chart code.",
                    "visual_type": "code",
                },
                {
                    "title": "Inspect The Incoming Data",
                    "body": "Unexpected data shapes can change what the chart component receives.",
                    "visual_type": "chart",
                },
                {
                    "title": "Compare Data And Rendering",
                    "body": "Look at the supplied structure alongside the chart output.",
                    "visual_type": "flow",
                },
                {
                    "title": "A Clearer Debugging Routine",
                    "body": "Check types, data shape, and rendering before assuming one cause.",
                    "visual_type": "learning",
                },
            ],
        }
        print("Using the reformatted, source-grounded Day 5 caption and standard five-slide template.")
    elif fixed_day6_standard:
        if topic != "Making chart components easier to extend":
            raise RuntimeError("The fixed standard template is only available for Day 6.")
        data = {
            "topic": topic,
            "post": (
                "Building chart components for different chart types means thinking about what should stay reusable and what may need to change. "
                "It is also useful to consider how the code can grow as requirements evolve.\n\n"
                "During my Techqueto internship, I worked with line, bar, area, and pie charts. "
                "The chart work was designed to be backend-ready and easier to extend, rather than assuming every future requirement in advance.\n\n"
                "My takeaway is to keep component responsibilities clear and make future changes easier to reason about. "
                "A flexible structure gives the next improvement a clearer place to start."
            ),
            "hashtags": ["ReactJS", "TypeScript", "FrontendDevelopment", "GoogleCharts"],
            "video_title": "Making Chart Components Easier to Extend",
            "slides": [
                {
                    "title": "Plan For More Chart Types",
                    "body": "Line, bar, area, and pie charts were part of the internship work.",
                    "visual_type": "chart",
                },
                {
                    "title": "Keep Shared Work Reusable",
                    "body": "Clear component responsibilities help related chart types remain understandable.",
                    "visual_type": "stack",
                },
                {
                    "title": "Leave Room For Change",
                    "body": "The chart work was intended to be easier to extend as requirements evolve.",
                    "visual_type": "flow",
                },
                {
                    "title": "Think Beyond Today’s Inputs",
                    "body": "Backend-ready design considers how data may be supplied later.",
                    "visual_type": "code",
                },
                {
                    "title": "Make Future Changes Clearer",
                    "body": "A flexible structure gives the next improvement a clearer starting point.",
                    "visual_type": "learning",
                },
            ],
        }
        print("Using the standardized, source-grounded Day 6 caption and five-slide template.")
    elif topic in {
        "Designing a product browsing and review flow",
        "Reusable navigation, product cards, and review sections",
        "Separating Truloop's frontend and backend",
        "Connecting Truloop's interface to backend APIs",
        "A look at Truloop's receipt proof validation",
        "Checking purchase dates against product release dates",
        "Validating the data required to submit a Truloop review",
        "Keeping product ratings current after a new review",
        "Organizing Truloop's routes by responsibility",
    }:
        data = source_grounded_fallback(topic)
        print("Using deterministic, source-grounded TruLoop content without depending on Gemini availability.")
    else:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it to GitHub Actions secrets.")
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
            fallback_topics = {
                "Replacing hardcoded chart values with JSON-driven data",
                "Understanding what happens behind the TruLoop interface",
                "Designing a product browsing and review flow",
                "Reusable navigation, product cards, and review sections",
                "Separating Truloop's frontend and backend",
                "Connecting Truloop's interface to backend APIs",
                "A look at Truloop's receipt proof validation",
                "What Truloop means by real usage experience",
                "Checking purchase dates against product release dates",
                "Validating the data required to submit a Truloop review",
        "Keeping product ratings current after a new review",
        "Organizing Truloop's routes by responsibility",
            }
            if topic not in fallback_topics:
                raise
            print(
                f"WARNING: Gemini generation failed for {topic!r} "
                f"({type(exc).__name__}: {exc}). Using verified, source-grounded fallback content."
            )
            data = source_grounded_fallback(topic)

    required = {"topic", "post", "hashtags", "video_title", "slides"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise RuntimeError("Generated content is missing required fields.")

    data["topic"] = topic
    data["source_facts"] = selected_topic["facts"]
    data["post"] = normalize_post_text(data["post"])
    data["video_title"] = clean_text(data["video_title"])[:180]

    word_count = len(data["post"].split())
    min_words, max_words = (95, 110) if (custom_binary_search or custom_java_polymorphism) else (70, 95)
    if word_count < min_words or word_count > max_words:
        # A malformed model caption is still a pre-publication generation failure.
        # For topics with verified deterministic content, fall back safely and
        # re-check the fallback rather than failing before the publisher runs.
        fallback_topics = {
            "Replacing hardcoded chart values with JSON-driven data",
            "Understanding what happens behind the TruLoop interface",
            "Designing a product browsing and review flow",
            "Reusable navigation, product cards, and review sections",
            "Separating Truloop's frontend and backend",
            "Connecting Truloop's interface to backend APIs",
            "A look at Truloop's receipt proof validation",
            "What Truloop means by real usage experience",
            "Checking purchase dates against product release dates",
            "Validating the data required to submit a Truloop review",
        "Keeping product ratings current after a new review",
        "Organizing Truloop's routes by responsibility",
        }
        if topic in fallback_topics and not (custom_binary_search or custom_java_polymorphism):
            print(
                f"WARNING: Generated caption for {topic!r} contained {word_count} words; "
                "using verified, source-grounded fallback content."
            )
            data = source_grounded_fallback(topic)
            data["topic"] = topic
            data["source_facts"] = selected_topic["facts"]
            data["post"] = normalize_post_text(data["post"])
            data["video_title"] = clean_text(data["video_title"])[:180]
            word_count = len(data["post"].split())
        if word_count < min_words or word_count > max_words:
            raise RuntimeError(f"Post body must contain {min_words} to {max_words} words, received {word_count}.")
    paragraphs = [paragraph for paragraph in data["post"].split("\n\n") if paragraph.strip()]
    if len(paragraphs) != 3:
        raise RuntimeError(f"Post body must contain exactly three paragraphs, received {len(paragraphs)}.")
    if "#" in data["post"] or any(
        re.match(r"^\s*(?:#{1,6}\s|[-*•]\s|\d+[.)]\s)", paragraph)
        for paragraph in paragraphs
    ):
        raise RuntimeError("Post body must be plain text without hashtags, headings, or list formatting.")
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
    used_layouts = set()
    for number, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise RuntimeError(f"Slide {number} is not a valid object.")
        title = clean_text(slide.get("title", ""))
        body = clean_text(slide.get("body", ""))
        visual_type = clean_text(slide.get("visual_type", "")).casefold()
        layout = clean_text(slide.get("layout", "")).casefold()
        raw_labels = slide.get("visual_labels", [])
        if not isinstance(raw_labels, list):
            raw_labels = []
        visual_labels = [clean_text(item)[:28] for item in raw_labels if clean_text(item)]
        if not title or not body:
            raise RuntimeError(f"Slide {number} is missing a title or body.")
        if len(title.split()) < 3 or len(title.split()) > 7:
            raise RuntimeError(f"Slide {number} title must contain 3 to 7 words for consistent mobile layout.")
        body_words = len(body.split())
        if body_words < 5 or body_words > 18:
            raise RuntimeError(f"Slide {number} body must contain 5 to 18 words.")
        if visual_type not in SLIDE_VISUAL_TYPES:
            raise RuntimeError(f"Slide {number} uses unsupported visual_type: {visual_type}")

        # Upgrade older fixed templates and ensure every frame has its own composition.
        if number == 1:
            layout = "hero"
        elif number == len(slides):
            layout = "closing"
        else:
            middle_layouts = {"split", "evidence", "process", "editorial", "detail"}
            if visual_type == "website":
                layout = "evidence"
            if layout not in middle_layouts or layout in used_layouts:
                available = [name for name in ["split", "evidence", "process", "editorial", "detail"]
                             if name not in used_layouts]
                if not available:
                    raise RuntimeError("Could not assign a distinct layout to every slide.")
                layout = available[0]
        used_layouts.add(layout)

        fallback_labels = {
            "chart": ["Line chart", "Bar chart", "Area chart", "Pie chart"],
            "flow": ["Input", "Process", "Response"],
            "code": [title, "Implementation detail", "Expected response"],
            "product": ["Product", "Specifications", "Reviews"],
            "database": ["Product", "Review", "User"],
            "form": ["Required fields", "Validation", "Submit"],
            "checklist": ["Check input", "Apply rule", "Return result"],
            "git": ["Change", "Review", "Improve"],
            "stack": ["Frontend", "Backend", "Database"],
            "learning": ["Understand", "Apply", "Test"],
            "website": ["Live TruLoop website", "Real interface", "Source screenshot"],
        }
        defaults = fallback_labels.get(visual_type, ["Input", "Process", "Response"])
        if not visual_labels:
            visual_labels = defaults[:]
        while len(visual_labels) < 3:
            candidate = next((item for item in defaults if item.casefold() not in {label.casefold() for label in visual_labels}), None)
            if candidate is None:
                break
            visual_labels.append(candidate)
        code_lines = slide.get("code_lines", [])
        if code_lines and (visual_type != "code" or not isinstance(code_lines, list)):
            raise RuntimeError(f"Slide {number} code_lines must be a list used only with visual_type 'code'.")
        code_lines = [clean_text(line)[:96] for line in code_lines if clean_text(line)] if isinstance(code_lines, list) else []
        if len(code_lines) > 10:
            raise RuntimeError(f"Slide {number} has too many code/trace lines for mobile readability.")
        cleaned_slides.append({
            "title": title,
            "body": body,
            "visual_type": visual_type,
            "layout": layout,
            "visual_labels": visual_labels[:4],
            **({"code_lines": code_lines} if code_lines else {}),
        })

    if cleaned_slides[0]["layout"] != "hero" or cleaned_slides[-1]["layout"] != "closing":
        raise RuntimeError("The video must begin with a hero composition and finish with a closing composition.")
    if len({slide["layout"] for slide in cleaned_slides}) != len(cleaned_slides):
        raise RuntimeError("Each slide must use a distinct composition.")

    website_count = sum(1 for slide in cleaned_slides if slide["visual_type"] == "website")
    if is_truloop_topic and website_count != 1:
        raise RuntimeError("TruLoop video must contain exactly one website slide using the genuine deployed screenshot.")
    if not is_truloop_topic and website_count:
        raise RuntimeError("Website screenshot slides are only allowed for TruLoop topics.")
    if any(mark in data["post"] for mark in chr(0x2014) + chr(0x2013)):
        raise RuntimeError("Post body must not contain em dash or en dash punctuation.")
    if any(0x1F1E6 <= ord(char) <= 0x1F1FF or 0x1F300 <= ord(char) <= 0x1FAFF or 0x2600 <= ord(char) <= 0x27BF for char in data["post"]):
        raise RuntimeError("Post body must not contain emojis.")

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
