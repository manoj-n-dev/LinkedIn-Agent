# 04 — Telegram Bot Design

**Version:** 0.1 — 20 October 2026
**Related files:** `02-prd.md` (FR IDs), `07-system-flows.md`, `09-content-rules.md`, `10-agent-rules.md`
Evidence labels: `01-project-vision.md` section 1.

---

## 1. Basics (for a beginner)

- A **Telegram bot** is an account run by a program. You create it by chatting with **@BotFather** and sending `/newbot`; it gives a secret **token**. If the token leaks, revoke it in BotFather (BRIEF-VERIFIED, B20/B21).
- **Inline keyboard** = buttons under a message. We use them for Approve / Reject.
- Use a **private chat only** (groups limit what bots see; B22).
- Two ways to receive messages (only one at a time): **long polling** (program keeps asking Telegram) or **webhook** (Telegram calls our web address). Webhooks support a secret token header (VERIFIED, V8).
- The bot cannot wake itself, so the daily briefing comes from the scheduled tick (`06-system-architecture.md`).

## 2. Command list

I kept all 15 of your commands and added two small ones. Reasons are in the table.

| Command | Does | FR | Notes |
|---|---|---|---|
| `/start` | Welcome and quick tour | FR-002 | Works only for the owner ID |
| `/help` | Command list | FR-002 | |
| `/status` | State of everything | FR-003 | |
| `/report` | Latest daily briefing (or regenerate) | FR-012 | |
| `/trends` | Topic scan from news, RSS, Hacker News | FR-012 | Never "trending on LinkedIn" |
| `/draft <idea>` | New post draft | FR-004, FR-005 | |
| `/comment` | Comment drafts for text you paste | FR-013 | Manual posting |
| `/connections` | Connection-note drafts and networking ideas | FR-014 | Never reads your connections |
| `/schedule` | Schedule an approved draft | FR-008, FR-009 | Needs publishing verified |
| `/approve` | Fallback to approve by draft code | FR-006 | Buttons are the main way |
| `/reject` | Fallback to reject by draft code | FR-006 | |
| `/history` | Recent items | FR-015 | |
| `/settings` | Change settings | FR-016 | |
| `/pause` | Stop all external actions | FR-017 | |
| `/resume` | Start again | FR-017 | Asks to confirm |
| `/connect` (added) | Link LinkedIn (sign-in) | FR-018 | Needed once every ~60 days |
| `/cancel` (added) | Cancel the current step | FR-006 | Safe exit from any flow |

## 3. General message rules

- Plain text by default. If formatting is used, all user or AI text is escaped so it cannot break the message or inject links.
- Telegram has a maximum message length; long texts are split at paragraph breaks, or shown as a summary plus a "Show more" button (FR-026). The exact limit: confirm in the Bot API docs (not re-opened by me).
- Button data is a **short random token** that the backend looks up, never the draft text (FR-027). Telegram limits button data size; confirm the limit in the docs.
- Every reply that changes something ends with what happened and what to do next.
- Anything from a stranger: no reply (see section 9).

## 4. Example conversations

### 4.1 First start
```
You:  /start
Bot:  Hi <display name, optional>. I am your private LinkedIn helper.
      I write drafts and briefings. I never post, like, comment or message
      by myself. You always decide.
      Type /help to see what I can do.
```

### 4.2 Draft, approve, publish (publishing on)
```
You:  /draft Share what I learned building my first Telegram bot
Bot:  Here is a draft (v1, 640 characters):
      ────────────
      <draft text>
      ────────────
      Code: D-7K2F    Visibility: Public
      [Approve & publish] [Edit] [New version] [Reject]
You:  (taps Approve & publish)
Bot:  Please confirm. This will post EXACTLY this text on your LinkedIn profile.
      Code D-7K2F, 640 characters. Valid for 30 minutes.
      [Yes, post it] [Cancel]
You:  (taps Yes, post it)
Bot:  Done. LinkedIn confirmed the post. Post ID: <id>.
```
If publishing is off: `Publishing is switched off. Copy the text above and post it yourself.`

### 4.3 Reject
```
You:  (taps Reject)
Bot:  Draft D-7K2F rejected. It will not be posted.
      [Write a new version] [Delete draft]
```

### 4.4 Comment drafts (manual)
```
You:  /comment
Bot:  Paste the text of the LinkedIn post you want to reply to.
      (I cannot read LinkedIn myself.)
You:  <pasted text>
Bot:  Here are 3 comment ideas. Copy one and post it yourself on LinkedIn:
      1) ...  2) ...  3) ...
      I did not send anything. [More ideas] [Done]
```

### 4.5 Connection note (manual)
```
You:  /connections
Bot:  Tell me who you want to write to and why (only what you are happy to share).
You:  <short description>
Bot:  Draft (178/200 characters, my safe limit):
      "..."
      Copy it and send it yourself from LinkedIn.
      Note: your account may allow only a few personal notes per month
      (the number is unconfirmed). Check your own account.
```

### 4.6 Unsupported request
```
You:  Like all posts from my network today
Bot:  I cannot do that. LinkedIn does not allow bots to like or comment,
      and it can restrict accounts that try. I can instead list posts
      or topics worth your attention from public sources. Want that?
```

### 4.7 Schedule
```
You:  /schedule D-7K2F tomorrow 9:00
Bot:  Schedule this exact text for Wed 21 Oct, 09:00 IST?
      My timer checks every ~15 minutes, so it may post a little late.
      If I miss the window by more than 30 minutes I will NOT post; I will ask you again.
      [Yes, schedule] [Cancel]
```

## 5. Approve and Reject layout

```
APPROVAL NEEDED
Code: D-7K2F        Version: 2        Hash: 9a41…c2e0
Visibility: Public  Length: 640
Expires: 11:42 IST (in 30 min)
────────────
<exact text to be published>
────────────
[✅ Approve] [❌ Reject]
[✏️ Edit]    [🔁 New version]
```
Rules:
- The text shown is read from the database at the moment of sending, and the approval is tied to its hash (SEC-013).
- After Approve, a second **confirmation** screen appears (see 4.2).
- After any edit, old buttons stop working: "This version is old. Use the newest message."
- Expired: "This approval ran out. Ask for a new one."

## 6. Confirmation and cancellation flows

| Action | Confirmation |
|---|---|
| Publish | Two steps: Approve, then "Yes, post it" |
| Schedule | One confirm with exact time |
| Turn publishing on | Confirm, and the audit log records it |
| `/resume` | Confirm |
| Delete or wipe data | Confirm; wipe needs the owner to type a word shown by the bot |
| Any flow | `/cancel` or [Cancel] ends it with no side effects |

## 7. Daily report layout

```
Good morning, <display name, optional> — briefing for Tue 20 Oct (IST)
Sources checked: 5 of 6   (1 failed: <name>)

1) <Headline>  — <source>, <date>
   Fact: <what the source says, in simple words>
   Why it matters (my interpretation): <one or two lines>
   Link: <url>
2) ...

POST IDEAS (suggestions, not facts)
• ...
COMMENT IDEAS (for posts you find yourself)
• ...
NETWORKING IDEAS (public events or discussions; contact people yourself)
• ...
NEXT ACTIONS
• ...
[More] [Draft a post from #2] [Settings]
```
If nothing reliable: `No reliable new information from your sources today. Nothing was invented.` If AI quota is out: headlines and links only, with a notice (FR-022).

## 8. Token-expiry warnings

```
Heads up: your LinkedIn login expires in 7 days (around 27 Oct).
After that I cannot publish. Tap /connect to sign in again.
```
Sent at 14, 7, 3 and 1 days before (PROPOSED) and once when expired. LinkedIn access tokens last 60 days; automatic refresh is only for a limited set of partners (**VERIFIED**, V3).

## 9. Unauthorized-user behaviour

- Any message, command or button from another user ID: **no reply**, no data change except a small counter row with a hashed ID (SEC-001, SEC-002).
- Rationale: replying would confirm the bot is alive and invite probing.
- Repeated attempts raise a quiet notice to the owner (at most once per day).

## 10. Error messages (wording)

| Case | Message |
|---|---|
| Publish failed | "LinkedIn did not accept it (reason: …). Nothing was posted." |
| Unknown result | "LinkedIn did not answer in time. I cannot tell if it posted. Please check your profile before trying again." [I checked: not posted] [It posted] |
| Rate limit | "LinkedIn says slow down. Nothing was posted. Try later." |
| Token expired | "Your LinkedIn login ended. Tap /connect." |
| AI problem | "The AI is not available right now. Your text is saved." |
| Paused | "I am paused. No LinkedIn actions will run. /resume to continue." |

## 11. Sources

V8 (webhook secret and ports), V3 (token life); BRIEF-VERIFIED: B20 https://core.telegram.org/bots/tutorial, B22 https://core.telegram.org/bots/faq, B23 https://core.telegram.org/bots/api, B24 https://core.telegram.org/bots/features.

## What I skipped or could not check

- Telegram message-length, button-data limit and rate limits were not re-opened by me.
- Nothing was tested in a real Telegram chat; all conversations are designs.
- LinkedIn note limits are UNCONFIRMED; the 200-character cap is my safe default.
- Your decisions: wording, emojis, expiry (30 minutes), scheduling grace window (30 minutes).
