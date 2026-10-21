# Onboarding & Setup Guide

This guide walks you through setting up and running your own private instance of the **LinkedIn Telegram AI Assistant** from a clean checkout.

---

## 1. Prerequisites

- **Python 3.12+** installed on your machine.
- A **Telegram account** (to interact with your bot).
- A free **Groq Cloud account** (to get a fast Llama 3 API key at [console.groq.com](https://console.groq.com)).
- *(Optional)* A **LinkedIn Developer Application** (if you want to enable official post publishing).

---

## 2. Quickstart Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/manoj-n-dev/LinkedIn-Agent.git
   cd LinkedIn-Agent
   ```

2. **Create and Activate Virtual Environment:**
   ```bash
   python -m venv .venv
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 3. Configuration

1. **Copy Environment Template:**
   ```bash
   cp .env.example .env
   ```

2. **Retrieve Your Telegram Bot Token:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram.
   - Send `/newbot`, choose a name and username.
   - Copy the API token provided and set it as `TELEGRAM_BOT_TOKEN` in `.env`.

3. **Find Your Numeric Telegram ID:**
   - Run the local helper tool:
     ```bash
     python -m src.owner_id_helper
     ```
   - Send any message to your new bot in Telegram.
   - The helper will print your numeric ID (e.g., `987654321`). Set this as `OWNER_TELEGRAM_ID` in `.env`.

4. **Get Your Groq API Key:**
   - Log into [console.groq.com](https://console.groq.com) and create an API key (`gsk_...`).
   - Set it as `GROQ_API_KEY` in `.env`.

5. **Generate Token Encryption Key:**
   - Generate a 32-byte Fernet key:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
   - Set it as `TOKEN_ENCRYPTION_KEY` in `.env`.

6. **Initialize the Database:**
   - For local development, the default SQLite database (`sqlite:///bot.db`) works out of the box:
     ```bash
     alembic upgrade head
     ```

---

## 4. Running the Bot Locally (Polling Mode)

Start the bot:
```bash
python -m src.main
```

Open Telegram, find your bot, and send:
```text
/start
```
You will receive the welcome screen! Only your Telegram account can interact with the bot; messages from strangers will be silently dropped.

---

## 5. (Optional) Enabling Official LinkedIn Publishing

By default, the bot runs in **drafts-only mode** (FR-020). To enable verified official publishing:

1. **Create LinkedIn Developer App:**
   - Go to the [LinkedIn Developer Portal](https://www.linkedin.com/developers/).
   - Create an app associated with your LinkedIn Page.
   - Under the "Products" tab, request:
     - **Sign In with LinkedIn using OpenID Connect**
     - **Share on LinkedIn** (grants `w_member_social`)
2. **Configure Redirect URL:**
   - In the "Auth" tab, add your redirect URI:
     - For local testing: `https://localhost:8000/callback/linkedin`
     - For Render hosting: `https://your-service.onrender.com/callback/linkedin`
3. **Update `.env`:**
   ```dotenv
   LINKEDIN_CLIENT_ID=your_client_id
   LINKEDIN_CLIENT_SECRET=your_client_secret
   LINKEDIN_REDIRECT_URL=https://your-service.onrender.com/callback/linkedin
   PUBLISHING_ENABLED=true
   ```
4. **Connect Account:**
   - In Telegram, send `/connect` to receive your authorization link.
   - Authorize in your browser, copy the `code` and `state` parameters from the redirect URL, and send:
     ```text
     /connect_token <code> <state>
     ```
   - Your account is now linked with tokens safely encrypted at rest!

---

## 6. Zero-Cost Cloud Deployment (Architecture B)

For full deployment instructions on Render free web service + Supabase PostgreSQL + GitHub Actions scheduler, see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

> **Important Notice on GitHub Actions Schedules:**
> On public repositories, GitHub automatically pauses scheduled workflow runs if there has been no repository activity for 60 consecutive days. A notice will appear in `/status` before this occurs; simply commit to the repository or manually trigger the workflow in GitHub's "Actions" tab to re-enable it.
