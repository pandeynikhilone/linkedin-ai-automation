# linkedin-ai-automation

Automation for creating LinkedIn posts and animated slide videos based on Nikhil Pandey's actual resume and public GitHub projects.

## Daily publishing
- The `Daily LinkedIn Career Content` workflow is scheduled for 9:37 AM Asia/Kolkata.
- It generates a post, 3 to 5 relevant hashtags, and a five-slide animated MP4.
- Scheduled workflow runs publish automatically when the required GitHub secrets and LinkedIn access remain valid.
- Manually running the daily workflow generates a preview and does not publish publicly.
- The `LinkedIn AI Content and Publishing` workflow remains a separate manual workflow.

## 30-day content plan
The sequence starts on 11 October 2026. Its 30 topics are grounded in the resume and existing GitHub repositories:
- Techqueto frontend internship: React, TypeScript, Google Charts, JSON-driven chart configuration, reusable chart utilities in `common.ts`, asynchronous loading with `useEffect`, and chart debugging.
- Truloop: product-review use case, Next.js frontend, reusable UI components, Express APIs, MongoDB, review submission validation, purchase-date checks, and the current receipt-text proof validation code using Tesseract.js and PDF parsing.
- TechFest: registration workflow, event selection, manual payment summary, admit card flow, the documented frontend/backend stack and role split, plus the resume's 8,000-plus registration figure.
- Resume-supported GitHub contribution information.

See [content-plan.json](content-plan.json) for the full 30-day topic list and the exact source facts used for each topic.

## Accuracy rules
Posts must be tied to the listed facts. The generator is instructed not to invent personal stories, achievements, metrics, results, technical features, or ownership of a collaborator's work. For Truloop's receipt validator, the code performs text-based checks and is not described as proof of genuine purchase.

## Required GitHub Actions secrets
- `GEMINI_API_KEY`
- `LINKEDIN_ACCESS_TOKEN`

The scheduled publishing flow also requires working GitHub Actions permissions and valid LinkedIn API access. A failed run must be reviewed in Actions before assuming a post was published.
