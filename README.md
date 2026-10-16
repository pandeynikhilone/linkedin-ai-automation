# LinkedIn AI Content and Video Automation

A goal focused content workflow that turns verified project work and learning into natural LinkedIn posts and five slide animated videos for an early career developer profile.

## Scheduled automatic publishing
- Scheduled for Tuesdays and Fridays at 09:00 Asia/Kolkata. Hourly recovery attempts continue through 14:00 IST if no publication is recorded.
- Uses a 30-topic learning series across the Techqueto internship, TruLoop, and the TechFest registration project.
- Writes 70 to 95 words of copy, with a hard maximum of 110 words.
- Captions aim for 70 to 95 words in three short paragraphs, with a specific hook, a verified technical detail, and a personal learning takeaway. Openings vary by topic. Captions use no emojis, headings, bullets, or inline hashtags, and avoid long dash punctuation.
- Produces exactly five slides with short titles, concise explanatory text, diagrams, and genuine screenshots of the deployed TruLoop homepage for TruLoop topics. The renderer does not recreate website UI.
- Renders a 1080 x 1350 portrait MP4 at 24 fps, with gentle movement and transitions.
- Encodes at 30 Mbit/s constant bitrate, the upper bitrate in LinkedIn's published member-video guidance. For the ~15.9-second clip this produces about 60 MB; the renderer and publisher reject files outside 50-70 MB.
- Uploads the MP4 through LinkedIn's Videos API, waits for processing to complete, then publishes the post text and video together through the Posts API.
- Scheduled runs publish automatically without per-post approval when the required APIs, credentials, and GitHub runner are available.
- Manually running the scheduled workflow creates a preview only. Use the separate manual publisher input when you intentionally want an immediate public post.
- A lightweight ledger preflight runs before FFmpeg, dependency installation, or Gemini. If today's India-local slot is already published, the generation/publishing job is skipped. Ambiguous `publishing` or `needs_review` entries stop safely for manual inspection.
- Scheduled posts upload directly to LinkedIn without duplicating the MP4 as an Actions artifact. Manual preview runs retain the video artifact for one day.
- If content generation, video rendering, upload, or LinkedIn processing fails, the workflow stops instead of publishing a text-only substitute.

## Thirty-topic content plan
Scheduled runs select the next topic after the most recently confirmed topic in `published-ledger.json` and wrap after Topic 30. Failed or uncertain attempts do not advance the sequence, so recovery runs retry the same topic. Every topic is grounded in the resume or public GitHub source. See [content-plan.json](content-plan.json) for the full list and supporting facts.

The plan covers:
- Techqueto: React, TypeScript, Google Charts, JSON-driven configuration, reusable utilities in common.ts, asynchronous loading, and debugging.
- TruLoop: Next.js, reusable UI components, Express APIs, MongoDB, review validation, purchase-date checks, and documented receipt text validation logic.
- TechFest: registration, event selection, manual payment summary, admit card flow, documented frontend and backend responsibilities, and the resume's 8,000-plus registration figure.

## Live dashboard

The live [LinkedIn Content Control Room](https://pandeynikhilone.github.io/linkedin-ai-automation/) shows all 30 plan topics, projected/actual dates, publication statuses, and links to confirmed posts. It checks its sanitized data feed every 30 seconds and redeploys after recognized requests or publication workflows finish. A scheduled refresh at 00:05 IST resets the dashboard's manual-publish availability for the new India-local date.

- Website: https://pandeynikhilone.github.io/linkedin-ai-automation/
- Website source: [dashboard/index.html](dashboard/index.html)
- Status feed builder: [scripts/build_dashboard_data.py](scripts/build_dashboard_data.py)
- Only the **next topic in the publication sequence** can be manually requested. The request workflow independently checks this against the last confirmed publication in `published-ledger.json`.
- The **Publish next post** button (or the enabled button on the next topic's row) opens a prefilled GitHub issue. As a static public website cannot safely hold a GitHub authorization token, click **Submit new issue** on GitHub to trigger the actual workflow. Only the repository owner’s issue can start publication.
- If a just-published post has a formatting problem, the owner-only correction workflow can publish one corrected replacement for the same topic on the same India-local date. It does not advance the plan beyond that topic or change the next Tuesday or Friday 09:00 IST scheduled slot.
- After a successful manual post, the publication ledger advances to the next topic. The automatic schedule runs on **Tuesdays and Fridays at 09:00 Asia/Kolkata**, with hourly recovery attempts through 14:00 IST. The manual post consumes the current local date's slot; it does not move the next scheduled Tuesday or Friday slot.
- The public status feed contains topic titles, dates, statuses, and confirmed LinkedIn post links only. **The repository itself is public**, so source files such as `content-plan.json` and `published-ledger.json` are also publicly readable. Never add tokens or other secrets to this repo.

## Preview a video before publishing
1. Open **Actions** and choose **LinkedIn Developer Story Video**.
2. Select **Run workflow**. Manual runs are preview-only.
3. Download the `linkedin-video-content` artifact.
4. Inspect `content.json` and play `linkedin_video.mp4`.
5. Scheduled runs begin automatically at 09:00 IST on Tuesdays and Fridays; video generation and LinkedIn processing may mean the post appears a few minutes later. Hourly recovery attempts continue until 14:00 IST if no publication is recorded.

## Required GitHub Actions secrets
- `GEMINI_API_KEY`
- `LINKEDIN_ACCESS_TOKEN`

Optional repository variable:
- `GEMINI_MODEL`, to choose the text-generation model.

The graphics are drawn locally by Python and Pillow, then animated and encoded by FFmpeg. For TruLoop posts, Playwright captures the actual deployed homepage and embeds that screenshot as footage. Other visuals use diagrams rather than fabricated website mockups.

## Accuracy and duplicate protection
- The post uses the topic's verified supporting facts and aims to sound like an MCA student describing actual work in straightforward language.
- Post copy is limited to 110 words.
- Do not invent personal stories, achievements, metrics, technical features, or results.
- TechFest contributions are attributed accurately. TruLoop's receipt text checks are not described as proof of genuine purchase.
- The publisher reserves each India-local date in `published-ledger.json` before upload, then records the confirmed result. Ambiguous failures are marked for review rather than blindly retried.

## API references
- [LinkedIn Videos API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api)
- [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api)
- [Gemini API documentation](https://ai.google.dev/gemini-api/docs)


LinkedIn's [video sharing requirements](https://www.linkedin.com/help/linkedin/answer/a7486279) list a 30 Mbps maximum bitrate for member video uploads. This workflow uses that bitrate target for its ~16-second clip and validates the expected 50-70 MB output range. The [Videos API documentation](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api) separately lists a 500 MB high-level file-size ceiling; file size alone does not override the bitrate guidance.
