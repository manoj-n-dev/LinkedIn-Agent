# Setup Guide (bring your own keys)

> **Status: planned.** The application code does not exist yet, so several steps below describe what setup **will** look like. Steps marked **(planned)** become real after the phase named in [`docs/12-implementation-plan.md`](docs/12-implementation-plan.md). Steps that use outside websites (BotFather, Groq, Supabase, GitHub, LinkedIn) describe the general idea; their screens and limits change, so follow the official page.

You will run **your own copy**. Nobody else needs your keys, and you should never share them. In this guide "you" means the person setting up their own copy.

## Before you start: what you need

| Item | Free? | Needed? |
|---|---|---|
| A Telegram account | Free | Yes |
| A GitHub account | Free | Yes |
| A Groq account | Free tier (limits can change; card requirement UNKNOWN — CHECK OFFICIAL DOCUMENTATION) | Yes |
| A database (Supabase free, or SQLite on your own computer for testing) | Free tier; Supabase pauses projects with low activity for 7 days and you can restore them | Yes |
| A host to run the bot | See [`docs/13-free-technologies-and-deployment.md`](docs/13-free-technologies-and-deployment.md). **No always-on free host is confirmed.** | For daily use |
| A LinkedIn Page and developer app | Free to create; approval steps apply | **Optional** (only to publish) |

Rule of thumb: **one account per service, your own.** Do not create several Groq accounts to get more quota; Groq's AI Policy names that as a way of exceeding limits.

## Step 1 — Get the code

1. Fork the repository, or use it as a template (whether template copies keep schedules on: UNCONFIRMED).
2. Keep your copy **private** while you set up. Make it public only if you want to, and only after you are sure no secret is in it.

## Step 2 — Create your Telegram bot

1. In Telegram, open **@BotFather** and send `/newbot`. Follow the questions. BotFather gives you a **token**: a secret password for the bot.
2. Treat the token like a password. If it ever leaks, revoke it in BotFather and make a new one.
3. Do **not** add the bot to a group. Use a private chat only.

## Step 3 — Create your settings file

1. Copy `.env.example` to a new file named `.env`.
2. Replace every `REPLACE_ME` with **your own** value. The app (planned, FR-028) refuses to start if any required value is missing or still a placeholder, and tells you only the **names** of the settings to fix.
3. Never commit `.env`. The `.gitignore` already blocks it. Never paste its contents into chats, issues or screenshots.

| Setting | What it is | Required? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from BotFather | Yes |
| `TELEGRAM_WEBHOOK_SECRET` | A long random string you make up (letters, numbers, `_`, `-`; 1 to 256 characters). Telegram sends it in a header so only Telegram can call your webhook | Yes, if you use a webhook |
| `OWNER_TELEGRAM_ID` | Your numeric Telegram user ID (Step 4) | Yes |
| `OWNER_DISPLAY_NAME` | Name used in greetings | Optional |
| `TIMEZONE` | For example `Asia/Kolkata` | Optional (default is the maintainer's) |
| `DATABASE_URL` | Your database address | Yes |
| `GROQ_API_KEY` | Your own Groq key | Yes |
| `GROQ_MODEL` | The model name you choose in the Groq console | Yes |
| `GEMINI_API_KEY` | Optional fallback. **Free tier content may be used to improve Google products**: public text only | Optional |
| `TOKEN_ENCRYPTION_KEY` | A key used to encrypt your stored LinkedIn token | Needed only with LinkedIn |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URL` | From your own LinkedIn developer app | Optional |
| `PUBLISHING_ENABLED` | `false` by default. Stays `false` until you have tested the official posting route yourself | Optional |
| `KILL_SWITCH` | `true` stops every LinkedIn-facing action | Optional |

## Step 4 — Find your Telegram user ID (planned, Phase 3, FR-029)

Only **your** ID may control the bot, so the app needs it. Instead of trusting a third-party "ID bot":

1. Start your bot's local helper (planned). Run it **before** you set a webhook, because only one way of receiving messages works at a time.
2. Send any message to **your own** bot from your Telegram account.
3. The helper prints the numeric ID of the sender. It stores nothing and does **not** make anyone the owner by itself.
4. Copy that number into `OWNER_TELEGRAM_ID` in your `.env`.

If a stranger messages your bot, they get **no reply** (FR-001).

## Step 5 — Run it on your own computer first (planned, Phases 2 to 8)

1. Use SQLite and polling mode. No LinkedIn is needed.
2. Send `/start`. You should get a reply; a second Telegram account should get **nothing**.
3. Try `/draft`, `/report`, `/comment`. These never call LinkedIn.
4. Run the test suite. It must pass **with no secrets set** (NFR-015).

## Step 6 — Optional: LinkedIn publishing (planned, Phases 9 and 10)

Skip this step if you only want drafts and briefings. Without it the bot runs in **drafts-only mode** and you post by hand.

1. LinkedIn developer apps must be linked to a **LinkedIn Page**. If you have none, create one. The Page's **super admin must approve** the link within 30 days, and the link cannot be moved later (BRIEF-VERIFIED, B44).
2. Create your own developer app and add the open products **Sign in with LinkedIn** and **Share on LinkedIn** (permission `w_member_social`, VERIFIED).
3. Add your own redirect URL (your host's address) to the app. Put the client ID, secret and redirect URL in your `.env` or host settings.
4. In Telegram, send `/connect` and sign in. LinkedIn access tokens last **60 days** and normal developers have no automatic refresh (VERIFIED), so you will sign in again about every 60 days; the bot warns you at 14, 7, 3 and 1 days.
5. **Test the posting route yourself.** Which endpoint works for a personal profile is UNCONFIRMED (`/v2/ugcPosts` in the Share on LinkedIn page, `/rest/posts` in the newer Posts API page). Do not switch `PUBLISHING_ENABLED` on until you have tested and recorded which one works.
6. Every post still needs your Approve tap on the exact text, then a second confirmation.

## Step 7 — Run it all day (planned, Phase 11)

Pick one plan from [`docs/13-free-technologies-and-deployment.md`](docs/13-free-technologies-and-deployment.md):

- **Architecture B:** a free web service (sleeps when idle; the first message after a quiet period can take about a minute), a free database, and a scheduled GitHub Actions job that runs the "tick" every ~15 minutes.
- **Architecture A:** one always-free virtual machine you manage yourself.

Put every secret in the **host's secret settings** and, for the tick, in **your own repository's** GitHub Secrets. Never in the code.

### Important GitHub rules for the scheduled tick (VERIFIED, 20 Oct 2026)

1. **Forks start with scheduled workflows disabled.** Open the Actions tab of **your** copy, enable workflows, and enable the schedule.
2. **In a public repository, scheduled workflows are switched off after 60 days with no repository activity.** If your daily briefing stops, check this first and re-enable the workflow. (What counts as "activity" is UNCONFIRMED.) A private copy or Architecture A avoids this, with other limits.
3. Workflows triggered from other people's forks **do not receive your secrets**, which is why tests use fake values only.

## Step 8 — Check that it is safe

- [ ] A second Telegram account gets no reply.
- [ ] `.env` is not in `git status`.
- [ ] `PUBLISHING_ENABLED` is `false` until you tested posting.
- [ ] `/pause` stops all LinkedIn-facing actions.
- [ ] You wrote down the date your LinkedIn sign-in ends.
- [ ] Your host and database passwords are not reused anywhere.

## If a key leaks

| What leaked | What to do |
|---|---|
| Telegram bot token | Revoke it in BotFather, make a new one, update your host secret, set the webhook again with a new secret |
| Groq key | Delete it in the Groq console, create a new one, update your host secret |
| Database password or URL | Rotate it in your database provider, update your host secret |
| LinkedIn client secret | Regenerate it in the LinkedIn Developer Portal; exact steps UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION |
| LinkedIn access token | Turn on `KILL_SWITCH`, remove the stored connection, revoke access using LinkedIn's official method (UNCONFIRMED), sign in again later |
| A secret was committed to git | Treat it as leaked. Deleting the file is **not** enough, because history keeps it. Rotate it |

More: [`docs/10-agent-rules.md`](docs/10-agent-rules.md) (rotation and incident runbooks).

## Troubleshooting (expected)

| Problem | Likely reason |
|---|---|
| App stops at start and lists setting names | A value is missing or still `REPLACE_ME` |
| Bot does not answer you | `OWNER_TELEGRAM_ID` is wrong, or the webhook secret does not match |
| First reply is very slow | Your free host was asleep (about a minute on some hosts) |
| Briefing did not arrive | GitHub schedule is off (fork, or 60 days without activity), or your free database paused |
| "Publishing is switched off" | Working as designed; copy the text and post by hand, or finish Step 6 |

## What I skipped or could not check

- The app does not exist, so none of the commands or helpers in this guide have been run.
- Telegram, Groq, Supabase, LinkedIn and GitHub screens and limits were not re-checked step by step; follow each provider's current official page.
- Whether Groq or others ask for a card, and what counts as "repository activity" on GitHub, are not confirmed.
- Whether a repository created from a template keeps schedules enabled is not confirmed.
