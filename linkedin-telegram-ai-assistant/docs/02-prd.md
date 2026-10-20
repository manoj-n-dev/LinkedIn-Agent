# 02 — Product Requirements Document (PRD)

**Version:** 0.1 — 20 October 2026 — planning only
**Related files:** `01-project-vision.md`, `04-telegram-bot-design.md`, `05-database-schema.md`, `06-system-architecture.md`, `07-system-flows.md`, `08-feature-roadmap.md`, `10-agent-rules.md`
Evidence labels are explained in `01-project-vision.md` section 1.

---

## 1. Product summary

A private Telegram bot, used only by the owner. It writes LinkedIn post drafts, comment drafts and connection-note drafts; sends a daily briefing from legal public sources; and, **only after the owner approves the exact text**, can publish the owner's own post through the official LinkedIn API (once that route is proven). It never scrapes, never automates the LinkedIn website, and never likes, comments, messages or invites on its own.

## 2. Target user

One person per deployment: the owner of that copy. There is no shared service and no second user inside one copy. Other people can run their own separate copies with their own keys (D-2, `01-project-vision.md` section 8A).

## 3. User stories

| ID | Story | Covered by |
|---|---|---|
| US-1 | As the owner, I want only me to control the bot, so that nobody else can use my account. | FR-001 |
| US-2 | I want to send a rough idea and get a post draft, so I save time. | FR-004, FR-005 |
| US-3 | I want to see the exact text and tap Approve or Reject, so nothing posts without me. | FR-006 |
| US-4 | I want an approved post to be published through the official API, so I do not copy and paste. | FR-007 |
| US-5 | I want to schedule an approved post, so it goes out at a good time. | FR-008, FR-009 |
| US-6 | I want a daily briefing at my chosen time, so I know what is happening in my topics. | FR-010, FR-011 |
| US-7 | I want comment drafts for posts I paste, so I can reply thoughtfully by hand. | FR-013 |
| US-8 | I want connection-note drafts, so I can write better notes by hand. | FR-014 |
| US-9 | I want a warning before my LinkedIn login expires. | FR-019 |
| US-10 | I want a pause button that stops every external action. | FR-017 |
| US-11 | I want clear honest messages when something fails or is not possible. | FR-020, FR-025 |
| US-12 | As someone using this project from GitHub, I want to use my own keys and bot, so that nobody else holds my credentials. | FR-028, FR-030 |
| US-13 | As a new user, I want to find my own Telegram user ID without trusting a third-party bot. | FR-029 |
| US-14 | As a user without a LinkedIn developer app, I still want drafts and briefings. | FR-018 (optional), FR-020 |

## 4. Functional requirements

Each requirement has a test. "Owner" means the Telegram user whose ID is set in the `OWNER_TELEGRAM_ID` setting (an environment variable).

| ID | Requirement | Test (how we know it works) |
|---|---|---|
| FR-001 | The bot acts only for the owner. Every update (message, command, button tap) from any other Telegram user ID is ignored: no reply, no feature access. Only a counter/audit row is stored. | Send commands and button taps from a second test account: zero replies, zero rows other than the unauthorized-attempt record. |
| FR-002 | `/start` and `/help` show a plain-English intro and the command list to the owner. The owner is identified by the configured ID, never by "first person to press /start". | Fresh database + owner ID set: `/start` from owner works; from another ID is ignored. |
| FR-003 | `/status` shows: paused or running, LinkedIn connection state and days until token expiry, publishing flag on/off, last and next briefing time, pending approvals, scheduled posts. | Compare output with database rows in a test. |
| FR-004 | `/draft <idea>` creates a post draft with the AI, saves it as version 1 (status `draft`), shows text and character count. | Mock AI returns text: one `drafts` row exists and the message shows the same text. |
| FR-005 | Editing or regenerating a draft creates a new version with a new content hash and **invalidates every earlier approval** of that draft. | Approve v1, edit to v2: v1 approval no longer usable; publishing v2 without a new approval is refused. |
| FR-006 | The approval request message shows the exact final text, its short hash code and the visibility choice, with Approve / Reject / Edit buttons. The approval record stores owner ID, content hash, expiry (default 30 minutes, PROPOSED) and is single-use. | Tap Approve after expiry: refused. Tap twice: second tap does nothing. Change text after request: Approve refused. |
| FR-007 | When publishing is enabled and an unused, unexpired approval for the exact hash exists, the backend calls the official LinkedIn post endpoint **once**, then reports the actual outcome (success with post ID, failure with reason, or unknown). | Mock API: success, 4xx, 429, 5xx, and timeout cases each give the correct message and database state. |
| FR-008 | `/schedule` accepts a draft and a future time in the owner's time zone (default IST). Approval is tied to the exact hash **and** the exact run time. | Schedule, change text: job refuses. Change time: needs new approval. |
| FR-009 | The owner can list and cancel scheduled posts. A cancelled post never publishes. | Cancel, run the job: no API call. |
| FR-010 | The daily briefing contains the nine parts in section 7 of the master prompt: developments, source links and dates, why it matters, facts vs AI interpretation, post topics, comment ideas, networking ideas, next actions, and a clear "no reliable new information" message when needed. | Mock sources: all sections present; empty sources: the "nothing reliable today" message appears and nothing is invented. |
| FR-011 | Briefing time, time zone, topics and sources are configurable in `/settings`; changes apply from the next run. | Change time to 09:30: next due time is 09:30 IST. |
| FR-012 | `/report` re-sends or regenerates the latest briefing. `/trends` scans the owner's topics using non-LinkedIn sources only. Neither ever says something is "trending on LinkedIn". | Search outputs for the phrase "trending on LinkedIn": absent. |
| FR-013 | `/comment` asks the owner to **paste the post text** (the bot cannot read LinkedIn), then returns 1 to 3 comment drafts. The flow ends with "copy and post it yourself". No LinkedIn call is made. | Network mock records zero calls to LinkedIn during the flow. |
| FR-014 | `/connections` returns connection-note drafts from details the owner pastes, and networking ideas from public sources. Default draft cap 200 characters (PROPOSED; the real limit is UNCONFIRMED). The bot never fetches or lists the owner's connections. | Drafts never exceed the cap; zero LinkedIn calls. |
| FR-015 | `/history` lists recent drafts, approvals, publish results and briefings with statuses. | Rows match database. |
| FR-016 | `/settings` shows and changes timezone, briefing time, topics, tone, language, and feature flags. Turning on publishing needs a confirmation step. | Flag changes are recorded in the audit log. |
| FR-017 | `/pause` blocks every LinkedIn-facing action and scheduled publish at once; `/resume` re-enables (with confirmation). A hard kill switch environment setting overrides everything. | Paused: approve + job both refuse to call LinkedIn. |
| FR-018 | `/connect` starts the LinkedIn sign-in with a one-time `state` value, asks only for the minimum scope, and stores the token encrypted. | Wrong or reused `state`: callback rejected. |
| FR-019 | The bot warns about LinkedIn token expiry at 14, 7, 3 and 1 days before, and when expired (PROPOSED schedule). | Set a fake expiry date: warnings appear once each. |
| FR-020 | Requests for unsupported features (likes, messages, auto-invites, reading the feed, profile viewers) get a short clear explanation and a safe alternative. No workaround is tried. | Ask for each: explanation shown, zero outbound LinkedIn calls. |
| FR-021 | Scheduled jobs survive restarts: overdue jobs run once on the next tick; the same job never runs twice for the same slot; a failed delivery is retried and finally reported. | Run the tick twice for one slot: one briefing. Skip a tick: catch-up works. |
| FR-022 | If the AI quota is exhausted or the AI call fails, the briefing is sent with raw headlines and links and a notice, or queued; the bot never switches to other accounts or keys. A second provider is used only if the owner enabled it. | Mock 429 from AI: fallback message appears. |
| FR-023 | Every approval decision and every external action writes an append-only audit row (no secrets). | Audit rows exist after each action. |
| FR-024 | The owner can delete drafts, history and context data, and wipe everything, each with a confirmation step. | After wipe: tables empty except settings the owner keeps. |
| FR-025 | The bot never reports success unless the API confirmed it. An unknown outcome (for example a timeout) is reported as unknown, never retried automatically, and the owner is told to check LinkedIn. | Mock timeout: message says unknown; no second API call. |
| FR-026 | Messages longer than the Telegram limit are split cleanly or summarised with a "more" button. | 10,000-character text: delivered as several valid messages. |
| FR-027 | Button taps carry a short random token, not the text itself, and each token works once. | Replay a tap: ignored. |
| FR-028 | **Bring-your-own configuration.** Every credential and ID (bot token, owner ID, AI key, database URL, LinkedIn client ID and secret, encryption key) comes from environment settings. The repository holds no real values. At start the app checks all required settings, rejects missing or placeholder values (such as `REPLACE_ME`), and prints the **names** of what is wrong, never the values. | Start with an empty environment, then with `.env.example` copied unchanged: both stop with a list of setting names; no value is printed. |
| FR-029 | **Owner ID setup helper.** A local command shows the numeric Telegram user ID of whoever sends a message to the deployer's own new bot, so it can be copied into `OWNER_TELEGRAM_ID`. It stores nothing and never makes that sender the owner by itself. This avoids asking people to use a third-party "ID bot". It must be run before a webhook is set (only one receiving method works at a time, B22). | Mock Telegram update: helper prints the sender ID and writes nothing to the database. |
| FR-030 | **No shared services and no telemetry.** The app contacts only: Telegram, the AI provider, configured research sources, the database, and (if enabled) LinkedIn's official hosts. No analytics, no error reports to the maintainer, no phone-home. | Test with a network mock and a host allow-list: any other host makes the test fail. |
| FR-031 | **Optional display name.** `OWNER_DISPLAY_NAME` (optional) is used in greetings; without it the bot says "Hi". | Unit test both cases. |

## 5. Non-functional requirements

| ID | Requirement | Test |
|---|---|---|
| NFR-001 | Recurring cost is zero. Any step that needs a card or payment is listed in `13-free-technologies-and-deployment.md`. | Review the list before each deployment. |
| NFR-002 | No secret appears in source code, logs, AI prompts, audit rows or Telegram messages. | Secret scanner on repo; grep of logs in tests. |
| NFR-003 | The bot acknowledges each command within 5 seconds when the host is awake. On a sleeping free host, the first reply can take about one minute (**VERIFIED** for Render free, V7). | Measure on the chosen host. |
| NFR-004 | The briefing is delivered within 30 minutes of its set time on 9 out of 10 days, excluding outages of free services (PROPOSED target; GitHub schedules can be delayed, UNCONFIRMED). | Review `job_runs` monthly. |
| NFR-005 | All times are stored in UTC and shown in IST by default. | Test with IST/UTC conversion cases. |
| NFR-006 | Logs contain no tokens, no full message bodies and no data about other people. | Log sample review in tests. |
| NFR-007 | Approval gate, ownership check, and idempotency have automated tests that must pass before any deployment. | CI result. |
| NFR-008 | Dependencies are few, pinned, and checked for known vulnerabilities. | Dependency audit report. |
| NFR-009 | Data retention follows `05-database-schema.md` section 9. | Cleanup job test. |
| NFR-010 | Backups of the database can be restored (tested once before real use). | Restore drill. |
| NFR-011 | Bot messages use simple English by default. | Manual review against `09-content-rules.md`. |
| NFR-012 | Unsupported or unknown features fail with an explanation, never silently with a different method. | FR-020 tests. |
| NFR-013 | **Clean public repository.** No secrets, personal IDs, personal names or private data in the files or in the git history. | Secret scan of the working tree and the full history before the first public push. |
| NFR-014 | **Beginner onboarding.** A new person can go from a fresh clone to a working `/start` reply by following `SETUP-GUIDE.md` alone. | One dry run by someone who did not write the code; record where they got stuck. |
| NFR-015 | **Fork-safe CI.** Automated tests use only fake values and need no secrets, so they also run on forks and on outside contributors' pull requests. | CI passes on a fresh fork with no secrets set. |

## 6. MVP scope

Detailed in `08-feature-roadmap.md`. In short: FR-001 to FR-006, FR-010 to FR-017, FR-019 to FR-031 and the audit log. **FR-007 to FR-009 (publishing and scheduling) are MVP-conditional:** built behind a feature flag that stays OFF until DIS-1 is settled by a real test in your developer app. FR-018 (LinkedIn sign-in) is needed only for those, and is **optional for every owner**: with no LinkedIn settings the app runs in drafts-only mode and the gate refuses every LinkedIn action with an explanation.

## 7. Future possibilities (only with evidence and your approval)

Weekly summary; image or link posts; reading notification emails from your own Gmail (MY IDEA, UNCONFIRMED, adds its own security duties); a second AI provider. See `08-feature-roadmap.md`.

## 8. Forbidden features

LinkedIn scraping, browser automation, unofficial APIs, passwords, session cookies, automated likes, comments, messages, connection requests or acceptance, evasion of LinkedIn limits, unauthorized feed or notification access, a shared or hosted bot that holds other people's keys, telemetry, real credentials in the repository, and any setting that switches a forbidden action on. Full list: `10-agent-rules.md` (POL-F rules). A human approval never makes a forbidden action allowed.

## 9. Acceptance criteria (whole product, MVP)

1. A stranger's Telegram account gets nothing.
2. A draft cannot be published without a matching, unexpired, unused approval, whatever the AI says and whatever a timer does.
3. A retry or timeout cannot create a second post.
4. The briefing arrives, is labelled fact vs interpretation, and contains no invented items.
5. `/pause` stops all LinkedIn-facing actions.
6. All tests for NFR-007 pass and are reported with real results.

## 10. Error states

| State | What the owner sees |
|---|---|
| Not authorised | Nothing (ignored). |
| Approval expired | "This approval ran out. Ask for a new one." |
| Content changed | "The text changed after approval. Approve the new text." |
| Publishing off | "Publishing is switched off. Here is your text to copy." |
| LinkedIn token expired | "Please sign in with LinkedIn again: /connect." |
| LinkedIn 429 or 5xx | "LinkedIn is busy. I did not post. I will not try again on my own." (or "Result unknown, check your profile" after a timeout) |
| AI quota exhausted | "AI limit reached. Sending headlines only." |
| Source down | Briefing notes which sources failed. |
| Unsupported request | Short explanation and the safe alternative. |

Exact wording lives in `04-telegram-bot-design.md`.

## 11. Accessibility and usability

Plain text first; emojis only as extra decoration, never the only signal. Short messages; buttons have text labels; no colour-only meaning; long text is split. Beginner-friendly wording.

## 12. Reliability requirements

Database-driven jobs; idempotency keys; catch-up after downtime; no automatic retries on LinkedIn-facing writes after unknown outcomes; every failure reported to the owner. No promise of 24/7 uptime on free hosting.

## 13. Privacy requirements

Store little. Never store other people's data by default. Comment and connection context is deleted after 7 days (PROPOSED). No raw tokens in logs or prompts. India's DPDP framework is considered (SEC-022). This is not legal advice.

## 14. Success metrics (no growth promises)

| Metric | Target (PROPOSED) |
|---|---|
| Briefings delivered on time | 9 of 10 days |
| Unauthorised actions executed | 0 |
| Posts published without matching approval | 0 |
| Duplicate posts | 0 |
| Draft turnaround | under 2 minutes when AI is available |
| Monthly cost | 0 |

## 15. Sources

- Posting and permission facts: V1, V2 (`01-project-vision.md` section 13).
- Token life: V3. Render sleep: V7. Telegram webhook secret: V8.
- LinkedIn automation rules: B2, B3, B10 (BRIEF-VERIFIED).

## What I skipped or could not check

- The exact Telegram character limit, button-data size limit and message-rate limit were **not re-opened** by me; the brief gives about 1 message per second per chat (B22). Confirm in the Bot API docs before building.
- Real LinkedIn connection-note limits (3 vs 5 per month; 200 characters) are UNCONFIRMED — check your own account.
- Whether the posting endpoint works for your personal profile (DIS-1) is unproven.
- Decisions for you: approval expiry (30 minutes), warning days, retention (7 days), target metrics.
- FR-028 to FR-031 and NFR-013 to NFR-015 are new (open-source model) and untested.
