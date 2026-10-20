# LinkedIn Telegram AI Assistant

A **private Telegram bot** that helps **one person** (you) with **your own** LinkedIn profile: it writes drafts, sends a daily briefing, and — only after you approve the exact text, and only if an official LinkedIn route is proven — can publish your own post.

> **Status: planning stage. There is no application code yet.** This repository currently holds the full design documents in [`docs/`](docs/). Nothing here has been built, deployed or tested against LinkedIn, Telegram or any AI provider. Do not expect a working bot today.

## What it is (and is not)

| It is | It is not |
|---|---|
| A drafting and briefing helper you control from Telegram | A LinkedIn automation bot |
| Owner-only: one person per copy | A shared or hosted service |
| Bring-your-own keys: **you** create your own bot, AI key and database | Something that holds anyone else's keys |
| Human approval for every post, tied to the exact text | A tool that likes, comments, messages or connects for you |
| Free-tier first (zero recurring cost is a goal, **not a guarantee**) | Guaranteed 24/7 uptime |

## What it will do (design)

- **Post drafts** from your ideas, with versions. Nothing is posted without your tap on the exact text.
- **Daily briefing** from public news, RSS feeds and the Hacker News API, with facts and AI opinion kept apart. It never claims something is "trending on LinkedIn".
- **Comment drafts** and **connection-note drafts** that you copy and send **by hand**.
- **Optional publishing** of your own post through the official LinkedIn API, switched **off** by default.
- Pause button and kill switch that stop every LinkedIn-facing action.

## What it will never do

No LinkedIn scraping, no browser automation, no unofficial APIs, no passwords or session cookies, no automatic likes, comments, messages or connection requests. A human approval does not make a forbidden action allowed, and no setting can switch one on. Full policy: [`docs/10-agent-rules.md`](docs/10-agent-rules.md).

## Bring your own keys

Every person runs **their own copy**. You will need (all free tiers, limits can change):

| You create | Used for | Required? |
|---|---|---|
| A Telegram bot (via @BotFather) | Your private control chat | Yes |
| A Groq account and API key (one account) | Drafts and summaries | Yes |
| A database (Supabase free, or local SQLite for testing) | Saving drafts, approvals, history | Yes |
| A host (see [`docs/13-free-technologies-and-deployment.md`](docs/13-free-technologies-and-deployment.md)) | Running the bot | Yes |
| A LinkedIn Page and developer app | Publishing your own post | **Optional** |

No real key or ID ever goes into this repository. Copy `.env.example` to `.env`, fill in **your** values, and keep `.env` private. Step by step: [`SETUP-GUIDE.md`](SETUP-GUIDE.md).

## Read the documents

| File | What it covers |
|---|---|
| [`docs/01-project-vision.md`](docs/01-project-vision.md) | Purpose, goals, risks, open-source model |
| [`docs/02-prd.md`](docs/02-prd.md) | Requirements (FR / NFR) |
| [`docs/03-tech-stack.md`](docs/03-tech-stack.md) | Chosen tools |
| [`docs/04-telegram-bot-design.md`](docs/04-telegram-bot-design.md) | Commands and messages |
| [`docs/05-database-schema.md`](docs/05-database-schema.md) | Tables and rules |
| [`docs/06-system-architecture.md`](docs/06-system-architecture.md) | How the parts fit |
| [`docs/07-system-flows.md`](docs/07-system-flows.md) | Step-by-step flows |
| [`docs/08-feature-roadmap.md`](docs/08-feature-roadmap.md) | MVP, later, never build |
| [`docs/09-content-rules.md`](docs/09-content-rules.md) | How AI text must be written |
| [`docs/10-agent-rules.md`](docs/10-agent-rules.md) | Allowed / needs approval / forbidden, plus security |
| [`docs/PONYTAIL.md`](docs/PONYTAIL.md) | Rules for coding agents |
| [`docs/12-implementation-plan.md`](docs/12-implementation-plan.md) | Build phases |
| [`docs/13-free-technologies-and-deployment.md`](docs/13-free-technologies-and-deployment.md) | Free hosting and tools |
| [`docs/14-antigravity-master-prompt.md`](docs/14-antigravity-master-prompt.md) | The prompt for building it |
| [`docs/15-open-questions.md`](docs/15-open-questions.md) | Decisions still open |

Evidence labels used everywhere: **VERIFIED** (an official page was opened on the date given), **BRIEF-VERIFIED** (taken from the research brief, not re-opened), **UNCONFIRMED**, **MY IDEA**, **PROPOSED**.

## Important notices

- **Not affiliated.** This project is not affiliated with, endorsed by or sponsored by LinkedIn, Telegram, Groq, Google or any other service it mentions.
- **Your accounts, your responsibility.** You are responsible for following the terms of every service you connect (LinkedIn, Telegram, your AI provider, your host). LinkedIn can restrict accounts; this project cannot prevent that.
- **No promises about results.** Nothing here promises followers, reach, engagement or connection growth.
- **Free tiers change.** Prices, limits and policies in the documents were checked on the dates written there and can change. Re-check before relying on them.
- **Not legal advice.** The notes about data-protection law (for example India's DPDP framework) are not legal advice.
- **Public repo and schedules.** On GitHub, scheduled workflows are switched off after 60 days without repository activity in a public repo, and forks start with schedules disabled. See [`SETUP-GUIDE.md`](SETUP-GUIDE.md).

## Contributing and security

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first. To report a vulnerability, read [`SECURITY.md`](SECURITY.md). Pull requests that add scraping, browser automation, automatic likes/comments/messages/invitations, telemetry, or real credentials will be closed.

## License

**Not chosen yet** (open decision Q-25 in [`docs/15-open-questions.md`](docs/15-open-questions.md)). Until a license file is added, nobody has a clear right to reuse the code.

## What I skipped or could not check

- No code exists, so nothing here is tested.
- LinkedIn's API Terms and brand rules for a public project could not be read (the page blocked automated reading), so any rule about distributing software built on the API is UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION.
- License, project name and support promises are decisions for the maintainer.
