# 07 — System Flows

**Version:** 0.1 — 20 October 2026
**Related files:** `04-telegram-bot-design.md`, `05-database-schema.md`, `06-system-architecture.md`, `10-agent-rules.md`
Evidence labels: `01-project-vision.md` section 1. Every flow is a **design**, nothing has been run.

Requirement references use `FR-`, `SEC-` IDs from `02-prd.md` and `10-agent-rules.md`.

---

## Flow 1 — Starting the bot

Goal: the app starts safely and refuses to run if the basics are missing.
```mermaid
flowchart TD
    A["App starts"] --> B{"Required secrets present?<br/>bot token, owner ID, DB URL, encryption key - none may be a placeholder like REPLACE_ME"}
    B -- no --> X["Stop with a clear error<br/>no secret printed"]
    B -- yes --> C{"Owner ID in env equals owner ID in DB?"}
    C -- mismatch --> X2["Stop and warn"]
    C -- ok --> D{"Kill switch on?"}
    D -- yes --> E["Start in SAFE mode: internal work only"]
    D -- no --> F["Register webhook with secret token<br/>or start polling"]
    F --> G["Ready"]
```
On a sleeping host, a cold start happens whenever Telegram calls after idle time (about 1 minute to wake, V7).

## Flow 2 — Authorizing the owner (every update)

```mermaid
sequenceDiagram
    participant U as Any Telegram user
    participant W as Web entry
    participant A as Authorization
    participant D as Database
    U->>W: message or button tap
    W->>W: check webhook secret header
    W->>A: user ID
    alt ID equals owner ID
        A->>D: record update ID (skip if seen)
        A-->>W: allowed
    else any other ID
        A->>D: count attempt with hashed ID
        A-->>W: ignore, no reply
    end
```
Applies to messages **and** callback queries (SEC-001, SEC-002).

## Flow 3 — Generating a post draft

```mermaid
sequenceDiagram
    participant O as Owner
    participant H as Handler
    participant AI as AI provider
    participant D as Database
    O->>H: /draft idea
    H->>AI: prompt with idea and tone (no secrets)
    AI-->>H: text
    H->>H: clean text, check length, compute hash
    H->>D: save draft v1 (status draft)
    H-->>O: show draft with buttons
```
If the AI is unavailable: "The AI is not available right now. Your idea is saved" (FR-022).

## Flow 4 — Approving and publishing a post

```mermaid
sequenceDiagram
    participant O as Owner
    participant H as Handler
    participant AP as Approval service
    participant G as External action gate
    participant L as LinkedIn client
    participant D as Database
    O->>H: Approve on draft code
    H->>AP: request approval (draft id)
    AP->>D: create approval row with content hash and expiry
    H-->>O: confirm screen with exact text
    O->>H: Yes, post it (callback token)
    H->>G: publish(draft id, approval id)
    G->>D: begin transaction
    G->>G: checks - owner, not paused, kill switch off, publishing on,<br/>approval approved, unused, unexpired, hash equals draft hash, token valid
    G->>D: mark approval used, create attempt row, commit
    G->>L: create post (official API)
    alt success
        L-->>G: post ID
        G->>D: attempt success, draft published, audit
        G-->>O: Done, post ID
    else refused
        G->>D: attempt failed, audit
        G-->>O: Not posted, reason
    else timeout
        G->>D: attempt unknown, audit
        G-->>O: Result unknown, check your profile
    end
```
If any check fails, nothing is sent to LinkedIn and the owner gets the exact reason (FR-007, FR-025).

## Flow 5 — Rejecting a draft

```mermaid
flowchart TD
    A["Owner taps Reject"] --> B["Callback token valid and unused?"]
    B -- no --> C["Ignore"]
    B -- yes --> D["Approval decision = rejected"]
    D --> E["Draft status = rejected"]
    E --> F["Audit row"]
    F --> G["Reply: rejected, will not be posted"]
```
A rejected approval can never be used (database check).

## Flow 6 — Scheduling a post

```mermaid
sequenceDiagram
    participant O as Owner
    participant H as Handler
    participant AP as Approval service
    participant D as Database
    participant T as Tick job
    participant G as Gate
    O->>H: /schedule code time
    H->>H: validate time in IST, must be future
    H->>AP: approval for hash AND run_at
    O->>H: confirm
    AP->>D: approval + scheduled_action (scheduled)
    Note over T: later, every ~15 min
    T->>D: due actions?
    T->>G: publish(action) - same checks as Flow 4
    alt window missed by more than 30 min
        G->>D: status skipped
        G-->>O: Not posted, please approve again
    end
```
A timer alone is never enough; the gate re-checks the approval (SEC-013).

## Flow 7 — Generating the daily briefing

```mermaid
sequenceDiagram
    participant T as Tick
    participant D as Database
    participant R as Research
    participant AI as AI provider
    participant TG as Telegram
    T->>D: insert job slot (unique)
    T->>D: briefing for today exists?
    T->>R: fetch configured sources
    R-->>T: items (title, url, date, text)
    T->>AI: summarise inside untrusted-data block
    AI-->>T: fact text and interpretation text per item
    T->>D: save briefing and items
    T->>TG: send to owner
    alt nothing reliable
        T->>TG: "No reliable new information today"
    end
```
Failures: AI quota out → headlines only; source down → listed as failed; Telegram delivery fails → retry up to 3 ticks, then a failure notice (FR-021, FR-022).

## Flow 8 — Generating comment drafts

```mermaid
flowchart TD
    A["Owner: /comment"] --> B["Bot asks owner to paste the post text"]
    B --> C["AI writes 1 to 3 drafts"]
    C --> D["Bot shows drafts with 'copy it yourself' note"]
    D --> E["Owner manually posts on LinkedIn"]
    E --> F["END - no LinkedIn call was made"]
```

## Flow 9 — Generating connection-note drafts

```mermaid
flowchart TD
    A["Owner: /connections"] --> B["Owner types who and why (own words)"]
    B --> C["AI writes short note, max 200 chars default"]
    C --> D["Bot shows draft and note-limit warning"]
    D --> E["Owner manually sends from LinkedIn"]
    E --> F["END - no LinkedIn call, no data about the person kept after 7 days"]
```

## Flow 10 — Token expiration and reauthorization

```mermaid
sequenceDiagram
    participant T as Tick
    participant D as Database
    participant O as Owner
    participant W as Web entry
    participant LI as LinkedIn sign-in
    T->>D: days left on token?
    T-->>O: warning at 14, 7, 3, 1 days
    O->>W: /connect
    W->>D: create one-time state
    W-->>O: sign-in link
    O->>LI: signs in and approves (minimum scope)
    LI->>W: callback with code and state
    W->>D: state valid and unused? mark used
    W->>LI: exchange code for token
    W->>D: store encrypted token, new expiry
    W-->>O: Connected
```
Token life is 60 days; normal developers cannot refresh automatically (V3).

## Flow 11 — API failure and retry

```mermaid
flowchart TD
    A["API call result"] --> B{"Which call?"}
    B -- "read-only (research, AI)" --> C{"Error type"}
    C -- "429 or 5xx or timeout" --> D["Wait, retry up to 3 times with growing pauses"]
    C -- "4xx other" --> E["Stop, report"]
    B -- "LinkedIn publish" --> F{"Outcome"}
    F -- "success" --> G["Record, tell owner"]
    F -- "clear refusal" --> H["Record, tell owner, no retry"]
    F -- "timeout or unclear" --> I["Mark UNKNOWN. NO automatic retry"]
    I --> J["Owner checks LinkedIn, then chooses:<br/>It posted / It did not post"]
    J -- "did not post" --> K["Needs a NEW approval"]
```

## Flow 12 — Duplicate-job prevention

```mermaid
flowchart TD
    A["Tick A and Tick B start together"] --> B["Both try to insert job_runs row for the same slot"]
    B --> C["Database allows only one"]
    C --> D["Winner runs the job"]
    C --> E["Loser stops"]
    D --> F["Briefing: run_date unique"]
    D --> G["Publish: approval_id unique in attempts"]
```

## Flow 13 — Unauthorized-user attempts

```mermaid
flowchart TD
    A["Stranger messages the bot"] --> B["Owner check fails"]
    B --> C["No reply"]
    C --> D["Store hashed ID counter"]
    D --> E{"More than 5 in a day?"}
    E -- yes --> F["One quiet notice to owner per day"]
```

## Flow 14 — Emergency shutdown

```mermaid
flowchart TD
    A["Owner sends /pause"] --> B["paused = true in DB"]
    A2["Owner sets KILL_SWITCH=true in host env"] --> C["Gate refuses all LinkedIn actions"]
    B --> C
    C --> D["Scheduled posts stay scheduled but are skipped while paused"]
    D --> E["Drafts, briefings, history still work"]
    E --> F["Owner can /resume with confirmation"]
    G["Worst case: revoke tokens (SEC-007)"] --> H["App cannot call LinkedIn at all"]
```
The environment kill switch works even if the bot or database is unreachable, because the gate reads it first.

## Flow 15 — First-time setup by a new owner (open-source model)

```mermaid
flowchart TD
    A["Clone or fork the repository"] --> B["Create own Telegram bot in BotFather"]
    B --> C["Copy .env.example to .env and fill own values"]
    C --> D["Send any message to the new bot"]
    D --> E["Run the local owner-ID helper: shows the sender ID, stores nothing"]
    E --> F["Put that ID in OWNER_TELEGRAM_ID"]
    F --> G["Start the app: missing or placeholder values stop it"]
    G --> H["Owner sends /start and gets a reply"]
    H --> I["Optional: create LinkedIn app, then /connect"]
    I --> J["Publishing stays OFF until the owner switches it on"]
```
Notes: the helper uses long polling, so run it **before** setting a webhook (only one method works at a time, B22). A stranger who finds the bot gets nothing (FR-001). On a fork, GitHub schedules start disabled (V13), so the owner must switch the tick on (see `SETUP-GUIDE.md`).

## Sources

V1, V2, V3, V7, V8 (`01-project-vision.md` section 13); B22 https://core.telegram.org/bots/faq.

## What I skipped or could not check

- Flows were not simulated or run; retry counts (3), warning days, 5-attempts rule and 30-minute window are PROPOSED values.
- LinkedIn's duplicate-post behaviour is unknown, so Flow 11 assumes none.
- Mermaid diagrams were not rendered by me; check them in a Markdown viewer that supports Mermaid.
- Your decisions: those numbers, and what you want when a briefing fails (open question Q-13).
