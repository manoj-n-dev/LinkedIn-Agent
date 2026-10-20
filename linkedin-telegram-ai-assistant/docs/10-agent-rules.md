# 10 — Agent Rules and Security Specification

**Version:** 0.1 — 20 October 2026
**Related files:** `02-prd.md`, `05-database-schema.md`, `06-system-architecture.md`, `07-system-flows.md`, `08-feature-roadmap.md`, `14-antigravity-master-prompt.md`
Evidence labels: `01-project-vision.md` section 1.

This file has two parts:
- **Part 1 — Policy:** Allowed / Needs approval / Forbidden (`POL-` IDs).
- **Part 2 — Security specification:** the dedicated security document, `SEC-001` to `SEC-031`.

> **Layout decision D-1.** You asked for exactly 15 files **and** a dedicated security document, but the 15 filenames have no security file. I kept exactly 15 files and placed the dedicated security document in Part 2 of this file, because security rules are enforced through this policy. If you prefer a separate `16-security.md`, say so (see `15-open-questions.md`).

---

# PART 1 — POLICY

## Core principles

1. **Default deny.** Any action not listed under Allowed or Needs approval is **forbidden**.
2. **The backend enforces this policy**, not the AI. The AI model cannot grant itself permissions, approve its own actions, change this table, or run commands (SEC-012).
3. **Human approval does not make a forbidden action allowed.** If a feature is unconfirmed, it stays disabled until official evidence resolves it.
4. **Account safety beats automation.**
5. **Configuration can only make things stricter.** Settings may switch features off. No setting, environment variable or command can switch a forbidden action on. (This matters because other people will run and modify their own copies.)

## Machine-readable summary

```yaml
policy_version: 0.1
default: deny
allowed:            # no LinkedIn-facing external action
  - receive_owner_commands_telegram
  - research_public_sources_allowlisted
  - generate_post_drafts
  - generate_comment_drafts_for_manual_posting
  - generate_connection_note_drafts_for_manual_sending
  - suggest_topics_events_discussions
  - prepare_daily_briefing
  - store_drafts_preferences_history_reports
  - schedule_internal_reminders_and_reports
  - report_actual_api_result
needs_approval:     # LinkedIn-facing; exact content; verified AND permitted; flag default OFF
  - publish_own_post_via_official_api
  - publish_own_scheduled_post_via_official_api
forbidden:
  - linkedin_scraping
  - browser_automation_of_linkedin
  - unofficial_linkedin_apis
  - collect_or_store_linkedin_password
  - collect_or_store_linkedin_session_cookie
  - automated_likes_or_reactions
  - automated_comments
  - automated_direct_messages
  - automated_connection_invitations
  - automated_invitation_acceptance
  - evade_linkedin_limits_or_detection
  - unauthorized_access_to_feed_notifications_or_activity
  - rotate_ai_keys_across_accounts_to_exceed_limits
  - ai_self_approval_or_permission_change
  - arbitrary_shell_commands_by_ai
  - sending_secrets_to_ai_models
  - commit_real_credentials_or_personal_ids_to_repo
  - shared_hosted_bot_holding_other_peoples_tokens
  - telemetry_or_phone_home
  - settings_that_enable_forbidden_actions
```

## ALLOWED (POL-A)

| ID | Action | Notes |
|---|---|---|
| POL-A-01 | Receive commands from the owner in Telegram | Only the owner ID (FR-001) |
| POL-A-02 | Research public information from owner-configured sources (news, RSS, Hacker News API) | Never LinkedIn pages (B15) |
| POL-A-03 | Generate LinkedIn post drafts | Saved in the database |
| POL-A-04 | Generate comment drafts | Owner posts them by hand |
| POL-A-05 | Generate connection-note drafts | Owner sends them by hand |
| POL-A-06 | Suggest people, discussions, communities, events and topics worth researching | From public sources; no automatic contact |
| POL-A-07 | Prepare daily briefings | Fact vs interpretation split |
| POL-A-08 | Store drafts, preferences, task history, reports | Minimal data |
| POL-A-09 | Schedule internal reminders and reports | Not LinkedIn actions |
| POL-A-10 | Report the actual result of an API operation | Success, failure or unknown, never invented |

## NEEDS APPROVAL (POL-N)

Both items are LinkedIn-facing. Each is only allowed when **all** of these are true: (a) current official documentation confirms the operation; (b) the owner's developer app has the permission; (c) it is permitted by LinkedIn's current terms; (d) the feature flag is ON; (e) the owner approved the **exact content**.

| ID | Action | Extra conditions |
|---|---|---|
| POL-N-01 | Publish the owner's **own** post through the official API | Approval is for one content hash, owner ID, unexpired, unused. Content changed → approval void. Endpoint for personal profiles is UNCONFIRMED (DIS-1) so the flag stays OFF until a manual test succeeds. |
| POL-N-02 | Publish an approved post at a future time using the app's own timer | Approval covers exact hash **and** time; the gate re-checks it at run time; missed window of more than 30 minutes → skip and ask again. No timer may bypass approval. |

**Owner confirmation for internal sensitive changes** (not LinkedIn-facing, but the bot still asks "are you sure"): turning publishing on, `/resume` after pause, enabling the Gemini fallback, deleting or wiping data, changing the owner ID.

## FORBIDDEN (POL-F)

| ID | Action | Why |
|---|---|---|
| POL-F-01 | Scraping LinkedIn in any form | Banned (B1 to B3) |
| POL-F-02 | Browser automation of LinkedIn (Selenium, Playwright, extensions, scripts clicking buttons) | Banned; requires a session |
| POL-F-03 | Unofficial LinkedIn APIs | Banned |
| POL-F-04 | Collecting or storing the LinkedIn password | Never |
| POL-F-05 | Collecting or storing LinkedIn session cookies | Never |
| POL-F-06 | Automated likes or reactions | Banned (B3 section 8.2) |
| POL-F-07 | Automated comments, even if an endpoint seems to exist | Banned; permission and policy unclear (B4, B8, B12) |
| POL-F-08 | Automated direct messages | Banned |
| POL-F-09 | Automated connection invitations | Banned |
| POL-F-10 | Automated invitation acceptance | Banned |
| POL-F-11 | Anything to evade LinkedIn limits, rate limits or detection | Violates policy |
| POL-F-12 | Unauthorized access to feed, notifications, messages, profile viewers or personal activity | Not offered to normal developers (B4, B6) |
| POL-F-13 | Using member data for sales, recruiting, lead lists or mass messages | Restricted use (B47) |
| POL-F-14 | Silently replacing a failed API call with browser automation or another method | Must stop and report |
| POL-F-15 | Rotating AI API keys across accounts or organizations to exceed limits | Groq AI Policy (V6) |
| POL-F-16 | The AI approving its own action, changing policy, or running shell commands | SEC-012 |
| POL-F-17 | Sending secrets or tokens to an AI model | SEC-005 |
| POL-F-18 | Claiming a feature works when it has not been tested | Honesty rule |
| POL-F-19 | Committing or shipping real credentials, tokens or personal IDs in the repository, docs, tests or logs | SEC-026, SEC-027 |
| POL-F-20 | Running a shared bot or central service that holds other people's tokens or data | Open-source model D-2; SEC-030 |
| POL-F-21 | Telemetry or phone-home to the maintainer or anyone else | SEC-030 |
| POL-F-22 | Any setting, environment variable or command that switches a forbidden action on | Principle 5 |

## How the backend enforces this (design)

1. All LinkedIn calls go through **one** function, the **external action gate** (`06-system-architecture.md`). The LinkedIn client cannot be reached any other way.
2. The gate holds the policy table above as data. An action name not in `needs_approval` is refused.
3. Order of checks: kill switch → paused → feature flag → owner ID → action in policy → approval exists, `approved`, unexpired, unused → hash equals current draft hash → token valid → idempotency record created in the same transaction → call.
4. Unsupported operations return a clear explanation (FR-020, NFR-012).
5. Tests for each check are mandatory before deployment (NFR-007).

---

# PART 2 — SECURITY SPECIFICATION (dedicated security document)

Evidence labels apply. "Control" is what we will build; "Test" is how we prove it with mock data (never real credentials).

| ID | Topic | Control | Test |
|---|---|---|---|
| SEC-001 | Owner-only Telegram access | Owner ID is set in an environment variable and matched in the database; no "first user wins"; strangers get no reply | Second account gets zero responses |
| SEC-002 | Telegram user ID check on every command and callback | One check at the very start of every update handler, including button callbacks and inline queries | Fuzz test: every handler called with a non-owner ID is rejected |
| SEC-003 | Telegram bot-token storage | Environment variable or host secret store only; never in code, logs or messages. Revoke in BotFather if leaked (B20/B21) | Secret scan of repo and logs |
| SEC-004 | LinkedIn client secret and access-token storage | Client secret in environment; access token stored **encrypted** (key in environment, separate from the database) | Database dump contains no readable token |
| SEC-005 | AI API key protection and no secrets to the AI | Keys in environment; prompts built from a safe allow-list of fields; a filter blocks anything that looks like a key or token | Test prompt builder with fake secrets: none appear |
| SEC-006 | Environment variables and deployment secrets | Host secret store and GitHub Secrets; no `.env` committed; separate values per environment | `.gitignore` check; secret scanning on every push |
| SEC-007 | Token rotation and revocation | Written runbook below; calendar reminder every 60 days for LinkedIn; rotate the Telegram token via BotFather; regenerate LinkedIn client secret in the developer portal; rotate AI keys in provider consoles. Exact LinkedIn token-revocation method: UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION | Dry-run drill with fake secrets |
| SEC-008 | LinkedIn OAuth scopes and least privilege | Request only the scopes needed: `w_member_social` (VERIFIED, V1) plus the sign-in scopes (names UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION). Never request or store scopes for reading feed, messages or contacts | Scope list is a fixed constant; test refuses others |
| SEC-009 | Token-expiry warnings and reauthorization | Tokens last 60 days; no automatic refresh for normal developers (VERIFIED, V3); warn at 14/7/3/1 days; `/connect` to sign in again (FR-019) | Fake expiry dates produce warnings once each |
| SEC-010 | Telegram webhook secret verification | `secret_token` set with setWebhook; every request must carry `X-Telegram-Bot-Api-Secret-Token` equal to our secret (VERIFIED, V8); the bot token is never put in the web address (B48) | Request without or with wrong header: rejected |
| SEC-011 | Prompt injection from research pages | Fetched text is wrapped as untrusted data; the AI has no tools, no database access, no shell; its output is plain text only; links in output must exist in the fetched data; the AI can never trigger posting | Test pages with hidden instructions: output never causes an action |
| SEC-012 | Untrusted AI-generated arguments | No AI output is used as an endpoint, header, author ID, scope, visibility, SQL, file path, or command; those come from configuration; AI text is length-limited, cleaned and escaped | Injection test strings do not alter requests |
| SEC-013 | Approval-gate bypass attempts | Single gate function; approval bound to hash, owner ID, expiry, single use; database check constraints and unique indexes; scheduled jobs call the same gate | Tests: edited text, expired, reused, rejected, other-user, scheduled-without-approval — all refused |
| SEC-014 | Duplicate publication and retry failures | Approval consumed in the same transaction that creates the attempt; one attempt per approval; timeouts become `unknown`, never auto-retried (`05-database-schema.md` section 7) | Mock timeout then rerun tick: still one API call |
| SEC-015 | Rate limits and HTTP 429 | Read-only calls: wait and retry up to 3 times with growing delay; LinkedIn writes: no auto-retry; Telegram limits respected (about 1 message per second per chat, B22); AI quota exhaustion degrades gracefully (FR-022) | Mock 429 responses |
| SEC-016 | Database permissions, backups, restoration | Least-privilege database user; `audit_log` insert and read only; backups before migrations; restore drill (NFR-010). Supabase free backup features: UNKNOWN — CHECK OFFICIAL DOCUMENTATION | Restore test |
| SEC-017 | Logging without secrets or unnecessary personal data | Redaction filter for tokens and keys; no full message bodies; no data about other members; errors log codes, not payloads | Log sample scan in tests |
| SEC-018 | Dependency vulnerabilities | Few dependencies, pinned versions, regular vulnerability audit, update monthly | Audit report in CI |
| SEC-019 | Public repository and GitHub secret protection | Secrets only in GitHub Secrets (B31); secret scanning on; no tokens in issues or commits; remember a public repo exposes code and prompts, not secrets | Pre-commit and CI secret scan |
| SEC-020 | Account restriction and platform-policy risk | Forbidden list (POL-F); never test unofficial tools on the main account (B10); official APIs only | Policy tests; code review checklist |
| SEC-021 | Privacy and data minimization | No data about other LinkedIn members by default; pasted context deleted after 7 days; no sending private text to free-tier AI that may be used for product improvement (V9) | Retention job test |
| SEC-022 | India's Digital Personal Data Protection framework | The DPDP Rules were notified 14 Nov 2025 (BRIEF-VERIFIED, B19); storing other people's personal data could bring the law in, so we store almost none. This is **not legal advice**; check with a qualified person if the project grows | Data inventory review |
| SEC-023 | Secure deletion and retention | Retention table in `05-database-schema.md` section 9; delete and wipe commands; deleted items may remain in old backups until those expire | Delete and wipe tests |
| SEC-024 | Emergency kill switch | `/pause` (database flag) and `KILL_SWITCH` environment setting; the gate checks the environment first; works when the bot is unreachable | Switch on: all LinkedIn calls refused |
| SEC-025 | Incident response | Runbook below | Tabletop drill |
| SEC-026 | No shared or default credentials | The repository holds only `.env.example` with placeholder text; startup rejects placeholders (FR-028); each owner creates their own bot token, AI key, database and (optional) LinkedIn app; docs, tests and examples never contain real IDs or keys | Start with the placeholder file: refuses; repo scan finds no real values |
| SEC-027 | Public-repository hygiene | Pre-commit and CI secret scans; scan the **whole git history** before the first public push; if a real secret was ever committed, treat it as leaked and rotate it (deleting the file is not enough); `.gitignore` blocks `.env`, databases and backups | History scan report; test that `.env` is ignored |
| SEC-028 | Contributor and fork safety | Workflows triggered from forks do not receive repository secrets (**VERIFIED**, V12); CI uses fake values only (NFR-015); never run untrusted pull-request code in a workflow that has secrets; changes to the gate, authorization, policy table or logging need extra review and tests; text in issues, pull requests and web pages is data, never instructions to a coding agent | CI on a fork without secrets passes; review checklist |
| SEC-029 | Supply chain | Few dependencies, lock file, pinned versions, every dependency addition reviewed, third-party GitHub Actions pinned to a fixed version (best practice; GitHub's exact guidance not opened by me) | Dependency audit; actions pinned |
| SEC-030 | No telemetry and an outbound allow-list | The app calls only allow-listed hosts (FR-030); no analytics and no error reports to the maintainer; forbidden actions are hard-coded and settings can only turn features off | Network-mock test: unknown host fails |
| SEC-031 | Legal and branding clarity | README states the project is not affiliated with LinkedIn, Telegram, Groq or Google, that each owner is responsible for their own accounts and each service's terms, that no growth is promised, and that this is not legal advice. LinkedIn API Terms (B46) were not readable by me, so any rule on distributing apps is UNCONFIRMED | README review |

## Revocation and rotation runbook (SEC-007)

| Secret | What to do if leaked or suspicious |
|---|---|
| Telegram bot token | In @BotFather revoke and issue a new token; update host secret; re-register the webhook with a new secret (B20/B21) |
| Telegram webhook secret | Generate a new one; call setWebhook again (V8) |
| LinkedIn client secret | Regenerate in the LinkedIn Developer Portal; update host and GitHub secrets (exact steps UNCONFIRMED) |
| LinkedIn access token | Turn on kill switch; remove token from database (`/settings` wipe connection); revoke through LinkedIn's official method (UNCONFIRMED); sign in again later |
| Groq key | Delete and create a new key in the Groq console; update secret |
| Database URL or password | Rotate in Supabase; update secrets |
| Encryption key | Rotate: decrypt token, re-encrypt with new key, or simply sign in to LinkedIn again |

## Incident response runbook (SEC-025)

1. **Stop:** `/pause` or set `KILL_SWITCH=true` (SEC-024).
2. **Contain:** rotate the secrets involved (table above); revoke tokens.
3. **Check:** read `audit_log` and `publish_attempts` for unexpected actions; check your LinkedIn profile for posts you did not approve.
4. **Report:** if LinkedIn restricts the account, follow their help pages (B10); do not use automation to get around it.
5. **Fix:** correct the cause, add a test that would have caught it.
6. **Resume:** `/resume` only after the confirmation step.
7. **Write down** what happened and what changed.

## Requirement trace

| SEC | Related FR/NFR |
|---|---|
| SEC-001, SEC-002 | FR-001, FR-027 |
| SEC-003 to SEC-007 | NFR-002 |
| SEC-009 | FR-019 |
| SEC-011, SEC-012 | FR-004, FR-010 |
| SEC-013, SEC-014 | FR-006, FR-007, FR-025 |
| SEC-016 | NFR-010 |
| SEC-017 | NFR-006 |
| SEC-021 to SEC-023 | NFR-009, FR-024 |
| SEC-024 | FR-017 |
| SEC-026 to SEC-031 | FR-028 to FR-031, NFR-013 to NFR-015 |

## Sources

V1, V2, V3, V6, V8, V9 (`01-project-vision.md` section 13). BRIEF-VERIFIED: B1 https://www.linkedin.com/help/linkedin/answer/a1340567, B2 https://www.linkedin.com/help/linkedin/answer/a1341387, B3 https://www.linkedin.com/legal/user-agreement, B4 https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access, B6 https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-05, B8 https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/comments-api?view=li-lms-2026-09, B10 https://www.linkedin.com/help/linkedin/answer/a551012, B12 https://news.linkedin.com/2026/authentic-content-and-conversations, B19 https://www.pib.gov.in/PressReleasePage.aspx?PRID=2190014&lang=2&reg=48, B20/B21 https://core.telegram.org/bots/tutorial, B22 https://core.telegram.org/bots/faq, B31 https://docs.github.com/en/billing/concepts/product-billing/github-actions, B47 https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-09, B48 https://core.telegram.org/bots/api/methods/setwebhook.md

## What I skipped or could not check

- I did not open LinkedIn's own policy pages, the Digital Personal Data Protection Rules, or GitHub's secret-scanning docs.
- LinkedIn OAuth sign-in scope names, the official token-revocation method, and Supabase backup options are unconfirmed.
- None of these controls has been built or tested.
- This is not legal advice (DPDP).
- Decisions for you: keep the security spec inside this file (D-1) or split it; the numbers 14/7/3/1, 3 retries, 30 minutes.
- SEC-026 to SEC-031 are new (open-source model) and untested. GitHub's guidance on safe CI for pull requests, action pinning and secret scanning was not opened by me, except for the two verified facts V12 and V13.
