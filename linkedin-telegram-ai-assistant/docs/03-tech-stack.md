# 03 — Tech Stack (smallest suitable set)

**Version:** 0.1 — 20 October 2026
**Related files:** `06-system-architecture.md`, `13-free-technologies-and-deployment.md`, `12-implementation-plan.md`, `PONYTAIL.md`
Evidence labels: see `01-project-vision.md` section 1. "Date checked" is 2026-10-20 for everything marked VERIFIED.

---

## 1. The selected stack at a glance

| Part | Choice | Status |
|---|---|---|
| Language | Python 3 (latest stable minor that all chosen libraries support) | PROPOSED |
| Telegram framework | `python-telegram-bot` | PROPOSED |
| Web framework | FastAPI (only for the Telegram webhook and the LinkedIn sign-in callback) | PROPOSED |
| AI provider | Groq free tier (one account, one key) | PROPOSED; limits UNKNOWN |
| Optional AI fallback | Gemini API free tier, **OFF by default** | PROPOSED |
| Database (production) | PostgreSQL on Supabase free tier | PROPOSED |
| Database (local/tests) | SQLite | PROPOSED |
| ORM and migrations | SQLAlchemy and Alembic | PROPOSED |
| Scheduler | An external "tick" trigger (GitHub Actions schedule, or system cron on a VM) running one idempotent job. **No in-app scheduler library.** | PROPOSED |
| HTTP client | `httpx` | PROPOSED |
| RSS parsing | `feedparser` | PROPOSED |
| Encryption of stored LinkedIn token | `cryptography` (Fernet) | PROPOSED |
| Testing | `pytest`, `pytest-asyncio`, `respx` (mocks `httpx`) | PROPOSED |
| Lint and format | `ruff` | PROPOSED |
| Code host | GitHub | PROPOSED |
| Dev environment | Google Antigravity (not a host) | BRIEF-VERIFIED |
| Hosting | See `13-free-technologies-and-deployment.md`: Architecture B (recommended start) or A | PROPOSED |

**Version policy.** Exact versions are `UNKNOWN — CHECK OFFICIAL DOCUMENTATION` today. At build time, pick the newest stable Python that `python-telegram-bot`, FastAPI, SQLAlchemy and `cryptography` all list as supported, pin it in the repo, and pin dependency versions in a lock file.

## 2. Why each choice (and what we left out)

### Python
You asked for Python. It is readable and well supported by AI coding tools. Nothing in the brief forces a change. TypeScript with grammY was the other option in the brief (B25, B26); we do not choose it because you prefer Python. (Cloudflare Workers fits TypeScript best, and its free plan allows only 10 ms CPU per request, V10; see file 13.)

### python-telegram-bot (chosen) vs aiogram (alternative)
Both are listed by Telegram (B25). Both support webhooks and inline buttons. **Why this one:** very common, good beginner documentation, easy to test. aiogram is a fine alternative; switching later is possible because Telegram code is isolated in one folder (`06-system-architecture.md`).

### FastAPI
We need a public web address for two things: Telegram's webhook calls (when using a host that sleeps) and LinkedIn's sign-in redirect. FastAPI is small and standard for that. Telegram webhooks can use ports 443, 80, 88 or 8443, must be HTTPS, and support a `secret_token` sent in the header `X-Telegram-Bot-Api-Secret-Token` (**VERIFIED**, V8).

### Groq (primary AI)
- Free tier exists. Rate limits apply **per organization** (**VERIFIED**, V4). The numbers on the page are ambiguous between "Free" and "Developer" plans (DIS-4), so: `UNKNOWN — CHECK YOUR OWN GROQ CONSOLE LIMITS PAGE`.
- **Data use (VERIFIED, V5):** by default Groq does not retain customer data for inference requests; data can be kept up to 30 days for reliability or abuse investigations; "Zero Data Retention" can be switched on in Data Controls by all customers. The page does **not** say whether Groq trains on your inputs: `UNCONFIRMED — CHECK GROQ TERMS AND PRIVACY POLICY`.
- **One account only (VERIFIED, V6):** Groq's AI Policy (effective 15 Oct 2025) bars going beyond rate limits and names registering multiple accounts as an example. **We do not design key rotation across accounts** (see `01-project-vision.md` section 8). Payment-method requirement: UNKNOWN — CHECK OFFICIAL DOCUMENTATION.
- **Open-source use:** each person who runs the project uses **their own** Groq account and key, one account each. The project never ships a key.
- Which model: not chosen here. Pick one in the Groq console at build time; note model names and limits change.

### Gemini (optional fallback, OFF by default)
**VERIFIED (V9):** on the free tier, "content used to improve our products" is **Yes**; Google Search grounding is not available on the free models listed; no numeric free limits are shown. Because of the data-use rule, it may only ever receive **public, non-private text** (for example public headlines to summarise), never your drafts' private context. It stays disabled until you enable it (FR-022).

### Database: PostgreSQL on Supabase, SQLite for development
- Supabase free projects with low activity for 7 days are **paused**; they can be restored from the dashboard for up to a year, and Supabase warns by email about a week before (**VERIFIED**, V11). A daily job normally counts as activity, but that is not guaranteed.
- Number of free projects, size limits, payment requirement: `UNKNOWN — CHECK OFFICIAL DOCUMENTATION` (the brief says 2 projects, B38/B39, not re-opened).
- SQLite is used **only** on your own computer and in tests. Free hosts like Render lose local files on restart (**VERIFIED**, V7), so SQLite there would lose data.
- Differences to remember: time zones, JSON columns and partial unique indexes behave slightly differently; tests should also run once against PostgreSQL.

### SQLAlchemy and Alembic
SQLAlchemy lets the code talk to either database. Alembic keeps database changes in numbered migration files so you can upgrade safely. Both are standard; no simpler tool gives migrations.

### Scheduler: no APScheduler, no Celery, no Redis
The bot cannot wake itself (B22). A free host may sleep. So the plan is **one idempotent "tick" command** that something external runs every 15 minutes. It checks the database: is a briefing due? is a scheduled post due and approved? is a token about to expire? what old data should be deleted? Because the database holds the truth, restarts, delays and double runs are harmless (FR-021).
- APScheduler was evaluated and **not selected**: it keeps timers in memory and needs an always-running process, which free hosts do not promise.
- GitHub Actions scheduled runs are free on public repos with standard runners; private repos have a limited quota (BRIEF-VERIFIED, B31). **VERIFIED (V13, opened 2026-10-20):** in a public repository, scheduled workflows are automatically disabled when there has been no repository activity for 60 days, and a forked public repository starts with scheduled workflows disabled. So a quiet public repo can silently stop its own tick, and every person who forks must switch the schedule on themselves. What counts as "activity" and how late a schedule can run: `UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION`. The bot must tell the owner when ticks stop (`06-system-architecture.md` section 7).

### httpx, feedparser, cryptography
- `httpx`: one HTTP client for AI, LinkedIn, Telegram file calls and RSS fetching, easy to mock.
- `feedparser`: reading RSS and Atom correctly is fiddly; one small library beats hand-written code (PONYTAIL rule: use a dependency only when it saves real work).
- `cryptography`: encrypts the LinkedIn token before it is saved (SEC-004).

### Tools deliberately not chosen
Redis, Celery, Kubernetes, microservices, multiple AI agents, n8n (not tested; needs a host), Selenium or Playwright (forbidden for LinkedIn), vector databases, paid search APIs (out of scope).

## 3. Hosting and deployment (summary)

Two realistic plans, fully compared in `13-free-technologies-and-deployment.md`:
- **Architecture B (recommended to start):** FastAPI webhook app on Render free (sleeps after 15 idle minutes, about 1 minute to wake, files lost on restart, Render says not for production — all **VERIFIED**, V7) + Supabase database + GitHub Actions tick.
- **Architecture A:** one Oracle Cloud Always Free VM running the app and a cron tick. More control, more server work, free-tier details BRIEF-VERIFIED only (B34).

**No reliable always-on free hosting is confirmed.** Antigravity is where code is written; it does not run the bot.

## 3A. Open-source (bring-your-own-keys) choices

| Topic | Choice | Status |
|---|---|---|
| License | Chosen by the maintainer. Permissive options exist (for example MIT or Apache-2.0). I did not pick one for you (Q-25). | UNKNOWN — decision needed |
| Repository files | `README.md`, `SETUP-GUIDE.md`, `SECURITY.md`, `CONTRIBUTING.md`, `.env.example`, `.gitignore`, `docs/` | PROPOSED |
| Config loading | Environment variables only; a small settings module checks them at start (FR-028) | PROPOSED |
| Secret scanning | A pre-commit hook plus a scan in CI. GitHub's own secret scanning and push protection for public repos: availability and plan UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION | PROPOSED |
| CI | GitHub Actions running tests with **fake values only**. Workflows triggered from forks do not receive repository secrets (**VERIFIED**, V12) | PROPOSED |
| Dependencies | Pinned in a lock file; every addition reviewed by hand | PROPOSED |
| Template or fork | People can fork or use a GitHub template. Forks start with schedules disabled (V13). Whether a repository created from a template behaves the same: UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION | UNCONFIRMED |

## 4. Secrets management

| Secret | Where it lives |
|---|---|
| Telegram bot token | Host environment variable / GitHub Secret |
| Telegram webhook secret | Same |
| LinkedIn client ID and secret | Same |
| LinkedIn access token | Database, **encrypted**, key from environment |
| Encryption key | Environment only |
| AI keys | Environment only |
| Database URL | Environment only |
| Owner Telegram ID | Environment variable |

A local `.env` file is allowed on your computer but is listed in `.gitignore` and never committed. Public repos use GitHub Secrets only (B31). Full rules: SEC-003 to SEC-007, SEC-019 in `10-agent-rules.md`.

## 5. Alternatives considered (short)

| Need | Alternative | Why not now |
|---|---|---|
| Framework | aiogram, grammY | Equal or language mismatch |
| Host | Railway, PythonAnywhere, Cloudflare Workers | See file 13 |
| AI | Gemini as primary | Free tier uses your content to improve products (V9) |
| Scheduler | APScheduler | Needs an always-on process |
| No-code | n8n | Not tested, needs a host, license limits unknown beyond personal use (B40) |

## 6. Known uncertainties

AI model choice and limits; Groq training policy; Supabase limits; Oracle signup requirements; GitHub schedule reliability; exact library versions; Telegram limits not re-opened.

## 7. Sources

V4–V13 (see `01-project-vision.md` section 13). BRIEF-VERIFIED: B25 https://core.telegram.org/bots/samples, B26 https://grammy.dev/resources/comparison, B31 https://docs.github.com/en/billing/concepts/product-billing/github-actions, B34 https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm, B38 https://supabase.com/docs/guides/platform/free-project-pausing, B40 https://docs.n8n.io/n8n-community-license/community-license/license-faq

## What I skipped or could not check

- I did not open the documentation of python-telegram-bot, FastAPI, SQLAlchemy, Alembic, httpx, feedparser, ruff or pytest, so library capabilities are PROPOSED from general knowledge, not VERIFIED.
- Groq training policy, payment requirement, and real limits; Supabase project count and storage; GitHub schedule behaviour.
- Decisions for you: keep one-account Groq; whether to allow the Gemini fallback; Architecture A or B.
- Open-source additions: license (Q-25), template-repo schedule behaviour, GitHub secret-scanning availability, and LinkedIn API Terms (B46: automated reading was blocked, so any rule about distributing apps is unconfirmed).
