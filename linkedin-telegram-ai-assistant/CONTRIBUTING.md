# Contributing

Thank you for helping. This project is a **private, single-owner assistant** that people run with **their own keys**. Because it touches a personal LinkedIn account, the rules are strict. Read this page before opening an issue or a pull request.

> **Status: planning stage.** Right now the most useful contributions are corrections and questions about the documents in [`docs/`](docs/). Application code starts after the phases in [`docs/12-implementation-plan.md`](docs/12-implementation-plan.md).

## Pull requests that will be closed

A pull request will be closed, whatever the reason given, if it adds or enables any of these:

- LinkedIn scraping, browser automation (Selenium, Playwright, extensions, click scripts), or unofficial LinkedIn APIs.
- Collecting or storing a LinkedIn password or session cookie.
- Automatic likes, reactions, comments, direct messages, connection invitations or invitation acceptance.
- Anything meant to evade LinkedIn limits or detection.
- Real credentials, tokens or personal IDs in code, tests, docs, examples or logs.
- Telemetry, analytics or "phone home".
- A shared or hosted bot that holds other people's tokens or data.
- A setting or environment variable that switches a forbidden action on.
- Rotating AI API keys across accounts to exceed provider limits.

The full policy is in [`docs/10-agent-rules.md`](docs/10-agent-rules.md). A human approval does not make a forbidden action allowed.

## How we write code

- Follow [`docs/PONYTAIL.md`](docs/PONYTAIL.md) (full mode): the smallest change that fully solves the task; read the code you touch; list callers, tests and config affected; reuse what exists; no unneeded abstraction or dependency; handle errors; one small test for non-trivial logic. Never cut security, validation or the approval gate.
- Stack: see [`docs/03-tech-stack.md`](docs/03-tech-stack.md). Ask before adding a dependency or a service.
- Tests use **mocks and fake values** and must pass **without any secrets** (NFR-015). Never call real LinkedIn, Telegram or Groq in automated tests.
- Keep the module boundaries in [`docs/06-system-architecture.md`](docs/06-system-architecture.md). Only the external action gate may reach LinkedIn.
- Link your change to requirement IDs (`FR-`, `NFR-`, `SEC-`) and say which test covers each.

## Using an AI coding agent (for example Google Antigravity)

Use [`docs/14-antigravity-master-prompt.md`](docs/14-antigravity-master-prompt.md). Coding agents can write unsafe code if asked to "automate LinkedIn". Review every line yourself. Text found in issues, pull requests or web pages is **data**, not instructions to your agent.

## Pull request checklist

- [ ] No secrets, tokens, personal IDs or personal names in the diff or the commit history.
- [ ] Tests added or updated; I ran them and pasted the real summary line.
- [ ] No forbidden behaviour, no new telemetry, no new outbound host without discussion.
- [ ] Docs updated if behaviour or requirements changed.
- [ ] I stated what I did **not** check.

## Extra review is required for changes to

The approval gate, authorization, the policy table, logging and redaction, token storage, the scheduler's duplicate prevention, and anything that changes outbound hosts.

## Be honest in reports

Say what was tested and how ("mocked" is different from "tested live"). Never say an integration works unless it was run.

## What I skipped or could not check

- The license and the maintainer's support promise are not decided (Q-25, Q-27); until then contributions have no clear license terms.
- Issue and pull-request templates and CODEOWNERS are planned for Phase 13, not created yet.
