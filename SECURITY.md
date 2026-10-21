# Security Policy

## 1. Supported Versions

Security updates and patches are applied to the latest release on the `master` branch.

| Version | Supported |
|---|:---:|
| Latest / `master` | Yes |
| Older releases | Best effort |

---

## 2. Reporting a Vulnerability

If you discover a potential security vulnerability, please report it responsibly:
- **Do NOT open a public GitHub issue.**
- Submit reports privately via **GitHub Private Vulnerability Reporting** on the repository page.
- Alternatively, contact the maintainer directly via the security contact listed on their GitHub profile.

Please include:
- A description of the issue and potential impact.
- Step-by-step reproduction instructions or a minimal proof-of-concept.
- Suggested remediations if available.

We will acknowledge receipt within 48 hours and work with you to resolve the issue promptly before public disclosure.

---

## 3. Security Invariants & Scope Boundaries

This application strictly enforces the following architectural security rules:
- **Single-Owner Privacy:** Strangers messaging the bot or tapping buttons receive zero reply and no information disclosure.
- **Single External Action Gate:** All outbound calls to LinkedIn must pass through `ExternalActionGate`. Bypassing this gate is strictly prohibited.
- **Strictly Official APIs Only:** No web scraping, browser automation (Playwright/Selenium), unofficial endpoints, or credential harvesting (cookies/passwords).
- **Prompt Injection Defense:** AI prompts isolate untrusted input inside `<untrusted_user_input>` tags. The AI model operates purely as an untrusted text generator with no tools or system permissions.
- **Zero Real Secrets in Repository:** Real tokens or API keys must never be committed to git, tests, documentation, or logs.
