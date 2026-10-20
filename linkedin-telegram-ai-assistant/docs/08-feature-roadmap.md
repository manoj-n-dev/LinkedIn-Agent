# 08 — Feature Roadmap

**Version:** 0.1 — 20 October 2026
**Related files:** `02-prd.md`, `10-agent-rules.md`, `12-implementation-plan.md`, `13-free-technologies-and-deployment.md`
Evidence labels: `01-project-vision.md` section 1.

Columns: **API** = what official API is needed. **Permission** = what permission. **Risk** = account/security risk. **Free?** = available under zero-cost.

---

## 1. MVP

| ID | Feature | Description | Depends on | API / Permission | Risk | Acceptance criteria | Free? |
|---|---|---|---|---|---|---|---|
| M-01 | Owner-only bot | Bot answers only the owner (FR-001, FR-002, FR-027) | Telegram bot token | Telegram Bot API | Low | Stranger gets nothing | Yes |
| M-02 | Post drafting | Idea → draft, versions, hash (FR-004, FR-005) | AI provider, DB | Groq | Low | Draft saved, edits invalidate approvals | Yes, within unknown AI limits |
| M-03 | Approve / Reject gate | Exact-text approval, expiry, single-use (FR-006) | DB | None | Low | See PRD tests | Yes |
| M-04 | Daily briefing | News, RSS, HN with facts/interpretation split (FR-010 to FR-012, FR-021, FR-022) | Research, AI, tick | RSS, HN API (B15) | Low | Briefing on time, honest when empty | Yes, host reliability varies |
| M-05 | Comment drafts (manual) | Owner pastes post, gets drafts (FR-013) | AI | None | Low | Zero LinkedIn calls | Yes |
| M-06 | Connection-note drafts (manual) | FR-014 | AI | None | Low | Zero LinkedIn calls, ≤ cap | Yes |
| M-07 | History, settings, pause/resume | FR-015, FR-016, FR-017 | DB | None | Low | Pause blocks external actions | Yes |
| M-08 | Audit log, kill switch | FR-023 | DB | None | Low | Rows exist; kill switch overrides | Yes |
| M-09 | Token expiry warnings | FR-019 | Connection stored | None | Low | Warnings at 14/7/3/1 days | Yes |
| M-10 | **LinkedIn sign-in** | FR-018 | LinkedIn Page + developer app | Sign in with LinkedIn (open product) | Medium | Reused state rejected; token encrypted | Yes; page and app setup needed (B44) |
| M-11 | **Publish own post (CONDITIONAL)** | FR-007; **flag OFF** until a manual test proves the endpoint for the owner's app (DIS-1) | M-03, M-10 | Share on LinkedIn, `w_member_social` (VERIFIED, V1) | Medium | One post, correct result message, no duplicates on timeout | Yes if proven |
| M-12 | Bring-your-own configuration and owner setup helper | Settings from environment only, placeholder rejection, local helper that shows your Telegram ID, optional display name (FR-028, FR-029, FR-031) | M-01 | Telegram Bot API | Low | Empty or placeholder settings stop startup, naming settings only | Yes |
| M-13 | Open-source onboarding kit | README, SETUP-GUIDE, SECURITY, CONTRIBUTING, `.env.example`, fork-safe CI, no telemetry (FR-030, NFR-013 to NFR-015) | All MVP | None | Low | A fresh-clone dry run reaches `/start` | Yes |

## 2. Later, subject to evidence and your approval

| ID | Feature | Description | Depends on | API / Permission | Risk | Acceptance criteria | Free? |
|---|---|---|---|---|---|---|---|
| L-01 | Scheduled post publishing | FR-008, FR-009 | M-11 proven | Same as M-11 | Medium | Missed window skips; approval re-checked | Yes if host runs ticks |
| L-02 | Weekly summary | Summary of the week's briefings | M-04 | None | Low | Facts vs opinion split | Yes |
| L-03 | Image or link posts | Posts with media | M-11 | Share on LinkedIn (V1 mentions image/article categories) | Medium | Same gate | Yes if proven |
| L-04 | Second AI provider (Gemini) | Fallback FR-022 | M-02 | Gemini (V9) | Privacy (free tier may improve Google products) | Public text only; OFF by default | Yes, limits unknown |
| L-05 | Better source management | Add/remove RSS from chat | M-04 | None | Low | Allow-list enforced | Yes |
| L-06 | Reading LinkedIn notification **emails** from your own Gmail | MY IDEA, **UNCONFIRMED**; reads email, which adds new duties | Gmail API terms | Gmail API (not researched) | Unknown, privacy-heavy | Needs a separate security review before any plan | Unknown |
| L-07 | Human-approved API comment or like | **BLOCKED.** Permission is unclear (`w_member_social` per older docs vs `w_member_social_feed` per newer, B4/B8) and policy is not addressed by LinkedIn (B3, B12). **Do not plan an implementation phase** unless LinkedIn gives an official statement that this is allowed. | Official evidence | Unclear | Medium to high | n/a until evidence | n/a |

Note on V1: the Share on LinkedIn page covers creating shares only; it does **not** cover comments or likes. V2 says `w_member_social` covers "post, comment, and like", but that wording is not a policy permission.

## 3. Never build (forbidden category)

| ID | Feature | Why never |
|---|---|---|
| N-01 | LinkedIn scraping (any form) | Banned (B1, B2, B3); lawsuits exist (B13) |
| N-02 | Browser automation of LinkedIn (Selenium, Playwright, extensions) | Banned; needs session cookies |
| N-03 | Unofficial LinkedIn APIs | Banned; account risk |
| N-04 | Collecting or storing LinkedIn password or session cookie | Security and policy |
| N-05 | Automatic likes or reactions | Banned (B2, B3) |
| N-06 | Automatic comments | Banned; reduced reach and possible restriction (B12) |
| N-07 | Automated direct messages | Banned |
| N-08 | Automated connection invitations or acceptance | Banned; no open invitation API (B4) |
| N-09 | Anything meant to evade LinkedIn limits or detection | Violates policy |
| N-10 | Reading the feed, notifications, profile viewers or messages without an official, authorized API | Not offered to normal developers |
| N-11 | Using lead lists or member data for sales or mass messages | Restricted use (B47) |
| N-12 | Rotating AI keys across accounts to exceed Groq limits | Prohibited by Groq's AI Policy (V6) |
| N-13 | "Control every pinpoint" of LinkedIn | Not available and not safe |
| N-14 | A shared or hosted bot that holds other people's tokens, keys or data | Single-owner design; security and privacy risk (D-2) |
| N-15 | Telemetry or phone-home to the maintainer or anyone else | SEC-030 |
| N-16 | Real credentials, tokens or personal IDs in the repository | SEC-026, SEC-027 |
| N-17 | Settings or environment variables that switch a forbidden action on | `10-agent-rules.md` principle 5 |

Full rules: `10-agent-rules.md` (POL-F). A human approval never turns a Never-build item into an allowed one.

## 4. Feature verdicts from the brief (kept)

| Wish | Verdict | Label |
|---|---|---|
| Post to own profile | YES | VERIFIED permission (V1); endpoint UNCONFIRMED (DIS-1) |
| Schedule posts (own timer) | YES | PROPOSED design |
| Comment on a post (API) | UNCLEAR → disabled | UNCONFIRMED |
| Like posts | UNCLEAR → forbidden | UNCONFIRMED and banned automation |
| Read own posts, comments, likes | NO | Restricted to approved users (V2, DIS-2) |
| Personal post analytics | NO | Community Management API is for registered organizations (B9) |
| Know "everything happening" | NO | No API (B4, B6) |
| Daily briefing | YES | Non-LinkedIn sources (B15) |
| Report from Gmail notification emails | MY IDEA | UNCONFIRMED |

## 5. Sources

V1, V2 (`01-project-vision.md` section 13); BRIEF-VERIFIED: B1 https://www.linkedin.com/help/linkedin/answer/a1340567, B2, B3, B4, B8 https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api?view=li-lms-2026-09, B9, B12 https://news.linkedin.com/2026/authentic-content-and-conversations, B13 https://www.bleepingcomputer.com/news/legal/linkedin-sues-proapis-for-using-1m-fake-accounts-to-scrape-user-data/, B15, B44, B47 (links in earlier files). Groq policy: V6.

## What I skipped or could not check

- I did not open B3, B8, B12 or B13 myself.
- Gmail API terms and free limits were not researched (L-06).
- Whether comments or likes via API are allowed for human-approved actions: no official statement found (the brief's finding; I did not find one either).
- Your decisions: which Later features you want, in what order.
- M-12, M-13 and N-14 to N-17 are new (open-source model) and untested.
