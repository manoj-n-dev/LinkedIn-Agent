# Operations & Deployment Runbook

**Architecture B:** Render Free Web Service + Supabase Free PostgreSQL + GitHub Actions Scheduler.

---

## 1. Zero-Cost Infrastructure Prerequisites

1. **Supabase PostgreSQL Database:**
   - Create a free project at [supabase.com](https://supabase.com).
   - Retrieve connection string: `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres`.
   - *Note on Inactivity:* Free projects pause after 7 days of inactivity. An automated maintenance ping during the daily briefing tick keeps the connection active.

2. **Render Web Service:**
   - Create a Web Service connected to your repository on [render.com](https://render.com).
   - Runtime: Python 3.12.
   - Build Command: `pip install -r requirements.txt && alembic upgrade head`.
   - Start Command: `uvicorn src.web.app:app --host 0.0.0.0 --port $PORT`.

---

## 2. Environment Configuration & Secret Registration

Set these environment variables in your Render Web Service dashboard:

| Variable | Description | Example / Note |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `123456789:ABCDefgh...` |
| `OWNER_TELEGRAM_ID` | Your numeric Telegram ID | `987654321` |
| `DATABASE_URL` | Supabase PostgreSQL connection string | `postgresql://...` |
| `GROQ_API_KEY` | One Groq API key | `gsk_...` |
| `GROQ_MODEL` | Default model | `llama-3.3-70b-versatile` |
| `TELEGRAM_WEBHOOK_SECRET` | Secret token for webhook verification | Random hex string |
| `TOKEN_ENCRYPTION_KEY` | 32-byte Fernet encryption key | Generated via Fernet |
| `LINKEDIN_CLIENT_ID` | (Optional) LinkedIn app Client ID | Set for official publishing |
| `LINKEDIN_CLIENT_SECRET` | (Optional) LinkedIn app Client Secret | Set for official publishing |
| `LINKEDIN_REDIRECT_URL` | Render callback URL | `https://your-service.onrender.com/callback/linkedin` |
| `PUBLISHING_ENABLED` | Publishing gate switch | `false` (default) |
| `KILL_SWITCH` | Emergency stop switch | `false` (default) |

---

## 3. Webhook Registration

Once your Render web service is live at `https://your-service.onrender.com`:

```bash
# Register Telegram Webhook with secret token (SEC-010):
curl -F "url=https://your-service.onrender.com/webhook/telegram" \
     -F "secret_token=YOUR_TELEGRAM_WEBHOOK_SECRET" \
     https://api.telegram.org/botYOUR_TELEGRAM_BOT_TOKEN/setWebhook
```

To verify webhook status:
```bash
curl https://api.telegram.org/botYOUR_TELEGRAM_BOT_TOKEN/getWebhookInfo
```

---

## 4. Cold-Start Behavior

- On Render Free, instances sleep after 15 minutes of inactivity.
- Inbound Telegram messages wake the instance automatically.
- Cold start wake time takes approximately 45–60 seconds. Telegram automatically retries update delivery, so messages are not lost.

---

## 5. Database Restore Drill Procedure (SEC-016)

Perform a quarterly restore drill to ensure recovery readiness:

1. **Dump Database:**
   ```bash
   pg_dump "postgresql://..." --clean --if-exists -f backup.sql
   ```
2. **Restore into Local Test Database:**
   ```bash
   psql "postgresql://localhost:5432/test_restore_db" -f backup.sql
   ```
3. **Run Health & Verification Tests:**
   ```bash
   pytest tests/test_database.py
   ```
4. **Clean up Backup File Immediately:**
   ```bash
   rm backup.sql
   ```
