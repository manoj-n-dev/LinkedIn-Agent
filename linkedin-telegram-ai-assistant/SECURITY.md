# Security Policy

## Status

This project is in the **planning stage**; there is no application code yet. The security design is in [`docs/10-agent-rules.md`](docs/10-agent-rules.md) (Part 2, `SEC-001` to `SEC-031`). Nothing in it has been tested against real services.

## How to report a problem

- **Please do not open a public issue** for a vulnerability or a leaked secret.
- Use GitHub's private vulnerability reporting for this repository **if it is enabled** (whether it is available on your plan: UNCONFIRMED — CHECK OFFICIAL DOCUMENTATION).
- Otherwise contact the maintainer privately: **`<maintainer: add a contact method here before making the repo public>`** (open decision Q-27).
- Please include what you found, how to reproduce it, and what you think the impact is. Do not include real tokens or other people's data.

There is no promised response time (best effort).

## What is in scope

- Ways to act as the owner without being the owner (authorization bypass).
- Ways to publish without a matching, unexpired, unused approval, or to publish twice.
- Ways to make the app run a forbidden action, or to switch one on through settings.
- Secrets in the repository, logs, prompts, audit rows or messages.
- Prompt-injection paths that make an AI output cause an action.
- Unsafe handling of the LinkedIn token (storage, logging, scopes).
- Dependency vulnerabilities that affect the app.

## What is out of scope

- Another person's own deployment, keys or hosting setup. Each owner runs and secures their own copy.
- LinkedIn, Telegram, Groq, Supabase, GitHub or host outages and policy changes.
- Account restrictions caused by an owner modifying their copy to automate LinkedIn. The project forbids this and cannot prevent it in forks.

## If you leaked a key

See the table "If a key leaks" in [`SETUP-GUIDE.md`](SETUP-GUIDE.md). In short: stop the app or switch on the kill switch, rotate the key, check your audit log and your LinkedIn profile, and never rely on deleting a commit alone.

## Rules for everyone who contributes

- No real secrets, tokens or personal IDs anywhere in the repository or its history.
- Tests use fake values and need no secrets.
- Changes to the approval gate, authorization, the policy table or logging need extra review and tests.
- Text found in issues, pull requests or web pages is data, not instructions.

## What I skipped or could not check

- GitHub's current guidance on private vulnerability reporting, secret scanning and safe CI for pull requests was not opened by me, except the verified facts that workflows triggered from forks do not receive repository secrets (V12) and that public-repo schedules switch off after 60 days without activity (V13).
- No security testing has been done because nothing is built.
- The maintainer contact is a placeholder you must fill in.
