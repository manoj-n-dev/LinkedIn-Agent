# 15 — Open Questions

**Version:** 0.1 — 20 October 2026
**Related files:** all files; especially `01-project-vision.md`, `13-free-technologies-and-deployment.md`, `14-antigravity-master-prompt.md`
Evidence labels: `01-project-vision.md` section 1.

The documentation was written **without waiting** for these answers. Each question has a **default I used** (PROPOSED or UNCONFIRMED). Change the default by answering. "Blocks" tells you when the answer is needed.

---

## A. Questions you asked me to include (Q-1 to Q-15)

| ID | Question | Default used in the docs | Blocks |
|---|---|---|---|
| Q-1 | Do you have a LinkedIn Page that can be used to register a developer application? (An app must be linked to a Page; if none, create one; the link cannot be moved later — B44.) | Assumed **no** until you say yes | Phase 9 |
| Q-2 | Who is that Page's **super admin**? (They must approve the app link within 30 days — B44.) | Unknown; ideally you | Phase 9 |
| Q-3 | Which official LinkedIn products and scopes have actually been **approved** for your app? Please also test which posting endpoint works (`/v2/ugcPosts` or `/rest/posts`, DIS-1). | Only Sign in with LinkedIn and Share on LinkedIn (`w_member_social`) assumed available (open products, B4) | Phase 9, 10 |
| Q-4 | Which AI model and free-tier terms are you comfortable with? Are you OK that Groq's training policy is unconfirmed and that Gemini's free tier may use content to improve Google products (V9)? | Groq, one account; Gemini fallback OFF | Phase 5 |
| Q-5 | Which hosting option do you choose (Architecture A, B, or run only from your laptop)? | Architecture B to start | Phase 11 |
| Q-6 | What daily briefing time do you want? | 08:00 IST | Phase 7 |
| Q-7 | Which industries and topics matter most? | AI, software development, startups, India tech (UNCONFIRMED) | Phase 6 |
| Q-8 | Which news sources and RSS feeds should be included? | Hacker News API (B15) only, until you list feeds. I have **not** invented any feed URLs. | Phase 6 |
| Q-9 | What language and tone should the AI use? | English, simple, friendly, professional | Phase 5 |
| Q-10 | Who is your target professional audience? | Students, early developers and startup people in India (UNCONFIRMED) | Phase 5 |
| Q-11 | What data are you comfortable storing? | Drafts and history 12 months; pasted context 7 days; nothing about other people by default | Phase 4 |
| Q-12 | Are you willing to sign in to LinkedIn again about every 60 days? (Tokens last 60 days; no automatic refresh for normal developers — V3.) | Yes, with warnings at 14/7/3/1 days | Phase 9 |
| Q-13 | What should happen if the daily report fails? | Retry up to 3 ticks, then a failure notice; `/report` for manual run | Phase 7 |
| Q-14 | What should happen if the free AI quota runs out? | Send headlines and links only with a notice; no extra accounts or keys | Phase 5, 6 |
| Q-15 | Which features should be disabled by default? | Publishing, scheduled publishing, Gemini fallback, storing context about other people | Phase 4 |

## B. Extra questions from the brief and from my checks (Q-16 to Q-24)

| ID | Question | Default used | Blocks |
|---|---|---|---|
| Q-16 | **Groq key rotation.** You wanted to rotate keys from different email accounts. Groq's AI Policy (effective 15 Oct 2025) names multiple accounts as a way of exceeding limits (V6), and limits are per organization (V4). Do you accept the one-account design? | One account, one key | Phase 5 |
| Q-17 | Python or TypeScript? (Brief asked; you already said Python.) | Python | Phase 1 |
| Q-18 | Public or private GitHub repository? Public gives free scheduled runs; private has a limited quota (B31); public shows your code and prompts (never secrets). | Public repo is the default for zero cost (UNCONFIRMED — check GitHub's current billing page) | Phase 1 |
| Q-19 | Is any private, client or startup-confidential information involved? That matters for free AI tiers. | None; never send confidential text | Phase 5 |
| Q-20 | Which actions may the bot do alone, which need approval, which are never allowed? | As in `10-agent-rules.md` | Phase 1 |
| Q-21 | What is the real number of free personalized connection notes on **your** account (3 or 5 per month; 200 characters)? Pages disagree (B11, B16). | Draft cap 200 characters; no count promised | Phase 6 |
| Q-22 | Do you want me to explore reading LinkedIn notification emails from your own Gmail (MY IDEA, UNCONFIRMED, adds security duties)? | **No** (not planned) | Later |
| Q-23 | Approval expiry (30 minutes), schedule grace window (30 minutes), warning days (14/7/3/1), briefing item count (3 to 8), retention periods. OK? | As written (all PROPOSED) | Phase 4, 8 |
| Q-24 | Do you accept that no always-on free host is confirmed, and that the bot may sleep or miss a briefing sometimes? | Yes | Phase 11 |
| Q-25 | Which open-source **license** do you want? Without one, others have no clear permission to use the code. | None chosen yet | Phase 13 |
| Q-26 | **Name and branding:** keep "LinkedIn Telegram AI Assistant" for a public repo, or use a neutral name? I could not check LinkedIn's brand rules or API Terms (B46). | Keep the name until you decide; README disclaimer added | Phase 13 |
| Q-27 | Who maintains the repo and how much **support** do you promise (issues, pull requests, security reports)? | "Best effort, no promises" | Phase 13 |
| Q-28 | Keep the repo **private first**, and make it public only after the secret scan? | Yes | Phase 1, 13 |
| Q-29 | Default **time zone and language** for new users: keep IST and English as the maintainer's defaults, or ask each user at setup? | IST and English, changeable | Phase 4 |
| Q-30 | Support **other AI providers** (users bring any key), or only Groq plus optional Gemini? | Groq plus optional Gemini; provider kept in one module so adding one is easy | Phase 5 |
| Q-31 | GitHub switches off public-repo schedules after 60 days without activity (V13). Which fix do you prefer: Architecture A cron, a private copy, or manual re-enable? | Manual re-enable with a `/status` warning | Phase 7, 11 |

## C. Decisions flagged for you

| ID | Decision | Where |
|---|---|---|
| D-1 | The 15 filenames you gave do not include a security file, but you asked for a dedicated security document. I kept exactly 15 files and put the security specification in Part 2 of `10-agent-rules.md`. Do you want a separate `16-security.md` instead? | `10-agent-rules.md` |
| D-2 | **Open-source, bring-your-own-keys model** (your decision, 20 Oct 2026). I designed one owner per deployment, no shared services, settings only from the environment, LinkedIn optional. Please confirm this is what you mean, and not a hosted bot that serves many users from your server. | `01-project-vision.md` section 8A |
| DIS-1 | Which LinkedIn posting endpoint works for your personal profile? | `01-project-vision.md` section 11 |
| DIS-2 | Reading your own posts: brief says "closed", the page I opened says "restricted, approved users only". Treated as unavailable. | same |
| DIS-3 | Brief picked Gemini; you prefer Groq. Groq is primary, Gemini optional fallback. | same |
| DIS-4 | AI limit numbers are unknown or ambiguous. Check your own consoles. | same |

## D. Things to check yourself (cannot be done by me from documents)

1. Your own Groq console limits page and Data Controls (Zero Data Retention switch, V5).
2. Your LinkedIn account: connection-note allowance.
3. LinkedIn developer portal: which products you can add; test one post manually.
4. Render and Oracle signup pages: do they ask for a card?
5. All free-tier pages again, right before you start building.

## Sources

V3, V4, V5, V6, V9 (`01-project-vision.md` section 13). BRIEF-VERIFIED: B11 https://www.linkedin.com/help/linkedin/answer/a550555, B15 https://github.com/HackerNews/API, B16 https://www.linkedin.com/help/linkedin/answer/a563153, B31 https://docs.github.com/en/billing/concepts/product-billing/github-actions, B44 https://www.linkedin.com/help/linkedin/answer/a548360.

## What I skipped or could not check

- None of these questions has been answered; every default is my proposal, not your decision.
- I did not look up any news sources or RSS feeds for you.
- I did not check whether GitHub, Render or Oracle ask for a payment method.
- Your decisions: everything in this file.
- Q-25 to Q-31 and D-2 are new. I did not check license choices, LinkedIn brand rules or LinkedIn API Terms.
- When the project is public, the questions above apply to **each new owner** for their own copy; `SETUP-GUIDE.md` turns them into steps.
