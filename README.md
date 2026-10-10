# LinkedIn AI Illustrated Content Automation

Daily LinkedIn posts based on Nikhil Pandey's resume and public GitHub projects. The format is one concise text post with one original AI-generated hand-drawn-style illustration. No video is generated or published by the active workflows.

## Daily unattended publishing
- Scheduled for 9:37 AM Asia/Kolkata every day.
- Uses the existing 30-day resume and GitHub topic plan.
- Writes a concise 70 to 95 word post, with a hard limit of 110 words, readable line breaks, optional short bullets, and 3 or 4 separate hashtags.
- Generates one square 2K editorial illustration with hand-inked lines, colored-pencil shading, restrained watercolor, and subtle paper texture.
- Exports an optimized 2048 x 2048 JPEG, a square format suitable for mobile, tablet, and desktop LinkedIn feeds.
- Uploads the image through LinkedIn's Images API and publishes the image with the post text through the Posts API.
- Scheduled runs publish without manual approval when credentials, API access, billing, and services are available. Manual runs are preview-only unless the manual publisher's public-post toggle is explicitly enabled.
- If image generation or LinkedIn publishing fails, the workflow fails safely. It will not publish text without its illustration.

## AI image cost
The default image model is `gemini-3.1-flash-image` at 2K resolution. Google's current standard API price is approximately **$0.101 per 2K image**, or about **$3.03 for 30 daily images**, excluding text-generation costs and taxes. This model has no free API tier. Billing must be enabled for the Gemini API key before the scheduled image-generation step can succeed.
- The existing `GEMINI_API_KEY` is used for both text and image generation if its billing setup supports the image model.
- An optional `GEMINI_IMAGE_API_KEY` secret may be set for a separate image key.
- Optional Actions variable `GEMINI_IMAGE_MODEL` can override the image model. The workflow requests 2K output.

## 30-day source-grounded content plan
The sequence starts on 11 October 2026. All 30 topics are based on the resume and public GitHub project details:
- Techqueto internship: React, TypeScript, Google Charts, JSON-driven configuration, reusable chart utilities in `common.ts`, asynchronous loading, and chart debugging.
- Truloop: Next.js frontend, reusable components, Express APIs, MongoDB, review validation, purchase-date checks, and the current receipt-text validation code.
- TechFest: registration flow, event selection, manual payment summary, admit card flow, the documented frontend/backend split, and the resume's 8,000-plus registration figure.

See [content-plan.json](content-plan.json) for all topics and their verified source facts.

## Preview or inspect a generated post
1. Open **Actions** and select **Daily LinkedIn Illustrated Career Post**.
2. Use **Run workflow** to generate a preview. Manual runs do not publish publicly.
3. Download the `linkedin-illustrated-content` artifact to inspect `content.json` and `linkedin_image.jpg`.
4. Scheduled runs publish automatically at the configured time.

## Required GitHub Actions secrets
- `GEMINI_API_KEY`
- `LINKEDIN_ACCESS_TOKEN`

Optional:
- `GEMINI_IMAGE_API_KEY`, if using a separate image-generation key.
- `GEMINI_MODEL` and `GEMINI_IMAGE_MODEL` repository variables, if selecting different model names.

## Accuracy and duplicate protection
- Every post is grounded in the day's topic facts and written in a natural voice suitable for an MCA student describing real work.
- The post is kept short and formatted with blank lines.
- No invented stories, achievements, metrics, product features, or outcomes.
- Truloop's receipt validator is described as a text-based check, not proof of genuine purchase.
- The publisher reserves each India-local date in `published-ledger.json` before calling LinkedIn. Ambiguous publishing failures are marked for review rather than blindly retried.

## Official API references
- [Gemini image generation](https://ai.google.dev/gemini-api/docs/image-generation)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [LinkedIn Images API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api)
- [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
