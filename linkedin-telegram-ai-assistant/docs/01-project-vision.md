# 01 — Project Vision

**Project name:** LinkedIn Telegram AI Assistant (name kept as you gave it; no rename proposed)
**Version:** 0.1 — written 20 October 2026 — **Stage: research and planning only. No code, no LinkedIn app, no deployment exists.**
**Related files:** `02-prd.md`, `03-tech-stack.md`, `08-feature-roadmap.md`, `10-agent-rules.md`, `15-open-questions.md`

---

## 1. How to read these documents (evidence labels)

Every claim in this project carries one of these labels, so nothing unproven becomes a "fact" by accident.

| Label | Meaning |
|---|---|
| **VERIFIED (opened 2026-10-20)** | I opened the official page myself on 20 Oct 2026 and read it. See the source key in section 13. |
| **BRIEF-VERIFIED** | Your research brief says it was read on the official page. I did **not** re-open that page. Treat as good but re-check before relying on it. |
| **SECONDARY** | From a non-official source (for example a newsletter). Not confirmed with the company. |
| **UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION** | Nobody has proven it. Stays disabled or undecided until proven. |
| **MY IDEA** | An idea from the brief, not tested, not verified. |
| **PROPOSED** | An engineering decision made in these documents. It is a choice, not a fact about the outside world. |

Requirement IDs used across files: `FR-` (functional), `NFR-` (non-functional), `SEC-` (security), `POL-` (agent policy rules). The security specification lives inside `10-agent-rules.md` (see decision D-1 in `15-open-questions.md`).

## 2. Project purpose

Build a **private helper for your personal LinkedIn profile**. You talk to it in Telegram. It thinks, researches and writes drafts. **You** approve anything that touches other people, and **you** do the clicking for comments, likes and connection requests.

## 3. The user problem

You are a student and startup founder in India. You want a stronger LinkedIn presence, but you have limited time, and your first idea ("an agent that controls every pinpoint of my LinkedIn, likes, comments, connections") is **not possible officially and not safe**:

- LinkedIn bans bots and automation for posting, commenting, liking, messaging and contacts (**BRIEF-VERIFIED**: User Agreement section 8.2, help pages).
- LinkedIn can restrict or close an account that automates (**BRIEF-VERIFIED**).
- Normal developers cannot read your feed, notifications, or personal analytics through an official API (**BRIEF-VERIFIED**).

So the honest product is a **thinking and drafting assistant with a strict approval gate**, not a LinkedIn robot.

## 4. Main goals

| ID | Goal |
|---|---|
| G-1 | Only you can use the bot (private, single owner). |
| G-2 | Turn your ideas into LinkedIn **post drafts** quickly. |
| G-3 | Publish **your own** post through the **official** API **only** after you approve the exact text, and only once the API route is proven to work for your app. |
| G-4 | Send a **daily briefing** at a time you choose, built from legal non-LinkedIn sources (news, RSS, Hacker News). |
| G-5 | Write **comment drafts** and **connection-note drafts** that you copy and send yourself. |
| G-6 | Keep drafts, history and settings safely stored. |
| G-7 | Cost nothing every month (a goal, not a guarantee — see section 8). |
| G-8 | Protect your LinkedIn account above everything else. |
| G-9 | Let other people on GitHub run **their own copy** safely, with their own API keys, bot token and IDs (D-2, section 8A). |

## 5. Intended user

**One owner per deployment.** The owner is whoever sets up their own copy of this project with their own keys. The maintainer's own use case (a beginner builder in India, time zone Asia/Kolkata) is the default example. Every document uses simple English and explains technical words once, because many owners will be beginners too. In these documents "you" and "the owner" mean the person running their own copy. This is **not** a hosted product: the maintainer does not run a shared bot for other people (see section 8A).

## 6. What success looks like

Success is about the tool working, **not** about LinkedIn numbers. (Nobody can promise followers, reach or connection growth.)

- You get a useful briefing most mornings at your chosen time.
- A draft is ready within a minute or two of sending an idea.
- Nothing is ever posted without your tap on the exact text.
- No LinkedIn rule is broken and the account stays healthy.
- You pay nothing, or you know exactly which service would start charging.
- You understand what each part does.

## 7. Project boundaries

**Inside the project**
- A private Telegram bot, a small Python app, a small database, a daily job.
- Drafting and research.
- Official LinkedIn API for **your own post** (Share on LinkedIn, permission `w_member_social`), if proven.
- Sign in with LinkedIn, only to link your account once.

**Outside the project**
- Anything that reads or controls LinkedIn through unofficial means.
- Anything for other people or other accounts.

## 8. Confirmed constraints (from you)

| Constraint | Value |
|---|---|
| LinkedIn account | Your personal profile only |
| Control | Private Telegram bot |
| Dev tool | Google Antigravity (writes code; it does **not** host the finished app) |
| Language | Python (change only with an explanation and your approval) |
| Automation | Mixed, with strict safety controls |
| Money | Zero recurring cost — free tools and free tiers only |
| Time zone | Asia/Kolkata (IST), changeable later |
| Database | PostgreSQL if a free one fits; SQLite only for local development |
| AI | Evaluate Groq free tier first (**see the warning on key rotation below**) |
| Users | One owner per deployment. On GitHub, other people run **their own copy** with their own keys (D-2) |

**Zero cost is a goal, not a promise.** Free services can sleep, pause, change limits, ask for a card, or disappear. `13-free-technologies-and-deployment.md` names each risk. **No reliable always-on free hosting is confirmed.**

### Warning about "rotating API keys from different email accounts"

I checked Groq's current AI Policy (effective 15 Oct 2025; **VERIFIED, opened 2026-10-20**). It says you must not go beyond published rate limits, and it names registering multiple accounts or splitting usage across organizations as an example of that. Groq's rate-limit page also says limits apply **per organization**, so extra keys inside one account share one quota.

**Decision for these documents (PROPOSED):** the design uses **one Groq account, one key**, with polite retries and a clear fallback when the quota runs out. It does **not** rotate keys across accounts. This protects you from losing your Groq access. You can overrule this, but I recommend you do not. See `03-tech-stack.md` and `15-open-questions.md` (Q-14).

## 8A. Open-source model (decision D-2, added 20 Oct 2026)

The maintainer decided to publish the project on GitHub so that other people can use it with **their own** API keys, bot token and IDs. Nothing is built yet; this is the design.

| Topic | Rule |
|---|---|
| Who runs it | Each person runs their own copy: own bot, own database, own AI key, own host. "One owner per copy" stays true (FR-001). |
| Shared services | None. No shared bot, database or keys; no tokens sent to the maintainer; no telemetry (FR-030, SEC-030). |
| Credentials | Never in the repository. Only `.env.example` with placeholders; the app refuses to start on placeholders (FR-028, SEC-026). |
| LinkedIn | Publishing is **optional**. An owner who wants it needs their own LinkedIn Page and developer app (B44). Without it, the app runs in drafts-only mode and the owner posts by hand. |
| AI | Each owner uses their own Groq account and key, one account each. Rotating accounts to exceed limits is still not supported (V6). |
| Responsibility | Each owner follows Telegram's, LinkedIn's and their AI provider's terms for their own accounts. The project promises no reach, growth or account safety. |
| Safety rules | The Forbidden list is hard-coded. Settings can switch features **off**, never a forbidden action **on** (`10-agent-rules.md` principle 5). |
| Branding | Not affiliated with LinkedIn, Telegram, Groq or Google. Whether the name is acceptable for a public repo under LinkedIn's brand rules: UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION (Q-26). |
| LinkedIn API Terms | I could not read them (the page blocks automated reading, B46). Any rule about distributing software built on the API is UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION. |
| GitHub schedules | **VERIFIED (V13):** in a public repo, scheduled workflows are switched off after 60 days with no repository activity, and a forked public repo starts with schedules disabled. Forked pull requests receive no repository secrets (**VERIFIED**, V12). |

## 9. Explicit non-goals

- Controlling "every pinpoint" of LinkedIn.
- Reading your feed, notifications, messages, profile viewers or personal analytics.
- Automatic likes, comments, direct messages, connection requests or invitation acceptance.
- Scraping, browser automation, unofficial APIs, passwords or session cookies.
- Guaranteed growth, reach or engagement.
- A hosted, shared or multi-user service run by the maintainer (a shared bot, shared keys, or holding other people's tokens or data).
- Telling you "this is trending on LinkedIn" (no source for that exists).

## 10. Key risks

| ID | Risk | Effect | Handling |
|---|---|---|---|
| R-1 | Account restriction from automation | Lose or limit your LinkedIn | Forbidden-actions policy, enforced in code (`10-agent-rules.md`) |
| R-2 | Posting API route not proven for personal profiles | Publishing may be impossible | Feature flag OFF until tested in your developer app (see DIS-1 below) |
| R-3 | LinkedIn token lasts 60 days | Publishing stops | Expiry warnings and re-login (**VERIFIED**: tokens last 60 days; automatic refresh only for a limited set of partners) |
| R-4 | Free hosting sleeps or loses files | Missed jobs | Database-driven job design, not memory-driven (`06-system-architecture.md`) |
| R-5 | Free AI quota runs out | No summaries | Degrade gracefully (FR-022) |
| R-6 | Free Gemini tier may use your text to improve Google products (**VERIFIED**) | Privacy | Never send private text; Gemini fallback is OFF by default |
| R-7 | Prompt injection from web pages the AI reads | Bad actions | The AI has no tools and no power; backend enforces rules (`10-agent-rules.md`) |
| R-8 | Leaked secrets | Account takeover | Env variables, revocation steps (SEC-003 to SEC-007) |
| R-9 | Storing other people's data | Privacy law (India DPDP) | Store almost none (SEC-021 to SEC-023) |
| R-10 | You break Groq's policy by rotating accounts | Lose AI access | Not designed in (section 8) |
| R-11 | A real key or ID is committed to the public repo | Account takeover for the owner | Secret scans, history scan before going public, placeholders only (SEC-026, SEC-027) |
| R-12 | GitHub switches off the scheduled tick (60 days without activity; forks start disabled, V13) | Briefings silently stop | Warning in `/status`, setup step to enable, fallback options in `13-free-technologies-and-deployment.md` |
| R-13 | Another owner automates LinkedIn by modifying their copy | Their account may be restricted; reputation risk for the project | Hard-coded forbidden list, README disclaimer, contribution rules; the project cannot control forks |
| R-14 | Branding or API-terms problem for a public project | Takedown or rule breach | UNCONFIRMED — check before going public (Q-26) |

## 11. Where the brief and today's official check disagree

These are **flagged for your review**. I did not silently replace the brief.

| ID | Brief says | Official page I opened today says | What I did |
|---|---|---|---|
| DIS-1 | Posting uses "the posts API" with fields author, lifecycleState PUBLISHED, content, visibility | The **Share on LinkedIn** page (last updated 2025-02-05 per its footer) documents `POST /v2/ugcPosts` with `w_member_social`. The newer **Posts API** page documents `POST /rest/posts` with a `Linkedin-Version` header; its example uses an **organization** author. | Both are written down. **Which one works for your personal profile with only the open "Share on LinkedIn" product is UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION** and must be tested in your developer app before building Phase 10. |
| DIS-2 | Reading your own posts (`r_member_social`) is "closed, no requests accepted" | The Posts API page says `r_member_social` is "restricted" and "available to approved users only". I did not re-open the FAQ page the brief cites. | Treat reading your own posts as **unavailable**. Do not promise it. |
| DIS-3 | Gemini free tier is the AI pick | You prefer Groq first | Groq is primary; Gemini is an optional fallback, OFF by default (privacy). |
| DIS-4 | Gemini limits "not confirmed" | Gemini pricing page shows **no numbers** for the free tier ("limited access to certain models"). Groq's page shows a table headed Free/Developer limits but with one set of values, so it is unclear which plan they describe. | All AI limits are `UNKNOWN — CHECK OFFICIAL DOCUMENTATION`. Read your own Groq console limits page. |

## 12. Assumptions requiring your confirmation

All are collected, with defaults, in `15-open-questions.md`. The main ones:

- You have, or can create, a LinkedIn Page (needed to register a developer app) and a super admin who approves it (**BRIEF-VERIFIED**: approval within 30 days; the link cannot be moved later).
- Daily briefing default time **08:00 IST** (PROPOSED).
- Default topics: AI, software development, startups (PROPOSED).
- Language English, simple professional tone (PROPOSED).
- Features OFF by default: publishing, scheduled publishing, Gemini fallback, saving context about other people.

## 13. Sources

**Source key.** `V#` = opened and read by me on 2026-10-20. `B#` = number in your brief's source list (BRIEF-VERIFIED, not re-opened).

| Key | Page |
|---|---|
| V1 | https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin |
| V2 | https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-05 |
| V3 | https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow |
| V4 | https://console.groq.com/docs/rate-limits |
| V5 | https://console.groq.com/docs/your-data |
| V6 | https://console.groq.com/docs/legal/ai-policy |
| V7 | https://render.com/docs/free |
| V8 | https://core.telegram.org/bots/api/methods/setwebhook.md |
| V9 | https://ai.google.dev/gemini-api/docs/pricing (first 100,000 of 126,749 characters read) |
| V10 | https://developers.cloudflare.com/workers/platform/limits/ |
| V11 | https://supabase.com/docs/guides/platform/free-project-pausing |
| V12 | https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows (first 100,000 of 115,240 characters read; secrets are not passed to workflows triggered from forks) |
| V13 | https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows (public repo schedules auto-disabled after 60 days of no activity; forks start disabled) |
| B46 | https://www.linkedin.com/legal/l/api-terms-of-use (**NOT read by me**: the page blocked automated reading) |
| B3 | https://www.linkedin.com/legal/user-agreement |
| B2 | https://www.linkedin.com/help/linkedin/answer/a1341387 |
| B10 | https://www.linkedin.com/help/linkedin/answer/a551012 |
| B44 | https://www.linkedin.com/help/linkedin/answer/a548360 |
| B45 | https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow |

A fetch of the Groq page `console.groq.com/docs/legal/your-data` failed once; the page at `console.groq.com/docs/your-data` (V5) loaded fine.

## What I skipped or could not check

- I did **not** open LinkedIn's own pages (User Agreement, help pages). Their rules here are BRIEF-VERIFIED only.
- I did not create a LinkedIn app, so DIS-1 (which posting endpoint works for you) is unresolved.
- Groq's page V5 is silent on whether Groq trains on your inputs; check Groq's terms and privacy policy.
- All AI free-tier numbers are unknown (DIS-4).
- Needs your decision: whether to follow my advice on Groq key rotation (section 8), and the defaults in section 12.
- Open-source additions (section 8A): LinkedIn API Terms and brand rules were not readable; license, name and support promises are undecided (Q-25 to Q-27); GitHub's definition of "repository activity" is unconfirmed.
