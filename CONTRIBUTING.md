# Contributing Guidelines

Thank you for your interest in contributing to the LinkedIn Telegram AI Assistant!

---

## 1. Core Architectural Rules

Before making any changes, please read [`docs/10-agent-rules.md`](linkedin-telegram-ai-assistant/docs/10-agent-rules.md). All contributions must respect these invariants:

1. **Owner-Only Authentication:** Every handler must be decorated with `@owner_only`. Unauthorized users must receive zero response.
2. **External Action Gate:** All LinkedIn operations must route exclusively through `ExternalActionGate`. Direct calls to `linkedin_client` from handlers or services are forbidden.
3. **No Unofficial Automation:** Any code attempting scraping, browser automation (Selenium/Playwright), session cookie capture, or automated engagement (likes, comments, DMs) will be rejected immediately.
4. **Prompt Isolation:** User-submitted ideas or scraped research must remain inside untrusted input delimiters. The AI must never be granted tools or system commands.
5. **Secret Hygiene:** Never commit real secrets, API keys, or personal credentials. Automated tests must use mock data and fake tokens only.

---

## 2. Local Development Workflow

1. **Clone and Setup Virtual Environment:**
   ```bash
   git clone https://github.com/manoj-n-dev/LinkedIn-Agent.git
   cd LinkedIn-Agent
   python -m venv .venv
   source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run Linter:**
   ```bash
   python -m ruff check .
   ```

3. **Run Test Suite:**
   ```bash
   python -m pytest -v
   ```
   *All tests must pass 100% before opening a pull request.*

---

## 3. Pull Request Guidelines

- Keep pull requests small, focused, and minimal (Ponytail philosophy: smallest change that fully solves the issue).
- Include comprehensive unit tests for any new logic or bug fixes.
- Ensure `ruff check .` outputs `All checks passed!`.
- Verify the secret scanner passes: `pytest tests/test_secret_hygiene.py`.
