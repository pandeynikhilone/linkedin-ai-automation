#!/usr/bin/env python3
"""Build the verified Day 15 long-form LinkedIn caption and ten slide scenes."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN_FILE = ROOT / "content-plan.json"
OUTPUT_FILE = ROOT / "content.json"
TOPIC = "Structuring review data with MongoDB"

POST = (
    "Database structure becomes important long before a feature feels complicated. A review feature needs a predictable way to represent what users submit, how the application reads it, and how that information is stored for later use. If the expected shape is unclear, the next developer has to guess which parts of the application depend on the same data.\n\n"
    "In TruLoop, my resume records work structuring MongoDB schemas to support review data, user submissions, and authentication workflows. A schema defines the expected shape of data that the application works with. That is useful because database design is not only about saving a document: it is also about making the data understandable to the code that creates, reads, or updates it. It still does not replace every business rule, authorization check, or validation step. Those responsibilities need to be handled in the application around the schema.\n\n"
    "When I think through a data model, I want to follow the information from the form or request into the stored document, then back to the feature that displays it. Clear structure gives me a better way to reason about changes and investigate unexpected results, without assuming that a schema by itself guarantees correctness or security. That distinction is useful across any full stack feature: define the data clearly, validate the rules explicitly, and make the path easy to trace. When you design a review feature, do you start with the document shape or the user flow?"
)

SLIDES = [
    {"title":"Start With The Data Model","body":"A review feature needs a predictable shape for the information an application stores.","visual_type":"database","layout":"hero","visual_labels":["MongoDB","Review data","User submissions"]},
    {"title":"Documents Need A Clear Shape","body":"A consistent document shape helps the application interpret stored review information.","visual_type":"database","layout":"split","visual_labels":["Document shape","Review fields","Stored data"]},
    {"title":"Schemas Describe Expected Structure","body":"A schema describes the expected structure that application code works with.","visual_type":"code","layout":"evidence","visual_labels":["Schema","Expected shape","Application model"]},
    {"title":"Follow A User Submission","body":"Trace information from user input through backend handling and into stored data.","visual_type":"flow","layout":"process","visual_labels":["User input","Backend handling","Stored document"]},
    {"title":"Support Reviews And User Workflows","body":"The documented schema work supports review data, user submissions, and authentication workflows.","visual_type":"stack","layout":"editorial","visual_labels":["Review data","User submissions","Authentication workflows"]},
    {"title":"Separate Shape From Business Rules","body":"A schema does not replace every validation or authorization rule the application must enforce.","visual_type":"checklist","layout":"detail","visual_labels":["Schema","Validation","Authorization"]},
    {"title":"Make Model Responsibilities Understandable","body":"Clear responsibilities help developers understand how application code works with stored documents.","visual_type":"database","layout":"split","visual_labels":["Application code","Data model","MongoDB documents"]},
    {"title":"Trace Data Before Debugging","body":"Follow input, validation, storage, and returned data before assuming where an issue starts.","visual_type":"flow","layout":"process","visual_labels":["Input","Validation","Storage","Response"]},
    {"title":"Avoid Claims A Schema Cannot Prove","body":"A defined structure alone does not guarantee correctness, security, or trustworthy user submissions.","visual_type":"learning","layout":"evidence","visual_labels":["Defined structure","Application rules","Accurate claims"]},
    {"title":"Design Data For Future Changes","body":"Clear document shapes give future changes a more understandable starting point.","visual_type":"learning","layout":"closing","visual_labels":["Clear structure","Readable models","Maintainable features"]},
]

def main():
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    topics = plan.get("topics", [])
    day15 = next((t for t in topics if int(t.get("day", 0)) == 15), None)
    if not day15 or day15.get("topic") != TOPIC:
        raise SystemExit("The verified Day 15 topic in content-plan.json has changed; refusing to guess.")
    facts = day15.get("sourceFacts", [])
    if not facts:
        raise SystemExit("Day 15 requires source-grounded facts in content-plan.json.")
    words = len(POST.split())
    if not 180 <= words <= 250 or len([p for p in POST.split("\n\n") if p.strip()]) != 3:
        raise SystemExit(f"Long-form caption must contain 180-250 words in three paragraphs, got {words}.")
    if re.search(r"[\u2013\u2014]", POST) or "#" in POST:
        raise SystemExit("Caption must use plain paragraphs, without long dashes or inline hashtags.")
    if len(SLIDES) != 10:
        raise SystemExit("Long-form videos require exactly ten slide scenes.")
    for i, slide in enumerate(SLIDES, 1):
        title_words = len(slide["title"].split())
        body_words = len(slide["body"].split())
        if not 3 <= title_words <= 7 or not 5 <= body_words <= 18:
            raise SystemExit(f"Slide {i} does not meet mobile text length limits.")
    if SLIDES[0]["layout"] != "hero" or SLIDES[-1]["layout"] != "closing":
        raise SystemExit("First scene must be hero and the final scene must be closing.")
    data = {
        "topic": TOPIC,
        "post": POST,
        "hashtags": ["MongoDB", "BackendDevelopment", "FullStackDevelopment", "MCAStudent"],
        "video_title": "Structuring Review Data with MongoDB: A Deeper Look",
        "slides": SLIDES,
        "source_facts": facts,
        "longform": True,
    }
    OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared source-grounded long-form content: {words} words, {len(SLIDES)} scenes, Day 15.")

if __name__ == "__main__":
    main()
