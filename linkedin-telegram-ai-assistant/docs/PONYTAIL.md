# PONYTAIL — Coding-Agent Rules (full mode)

**Version:** 0.1 — 20 October 2026
**Related files:** `12-implementation-plan.md`, `14-antigravity-master-prompt.md`, `10-agent-rules.md`
Evidence labels: `01-project-vision.md` section 1.

**Source:** the rules below are copied in summary from your research brief (section 10), which says it read `github.com/DietrichGebert/ponytail` (files `AGENTS.md` and `skills/ponytail/SKILL.md`, MIT license). **BRIEF-VERIFIED. I did not open the repository myself**, so wording may differ from the current repository. Check it before relying on exact text: https://github.com/DietrichGebert/ponytail

---

## 1. When these rules apply

| Situation | Applies? |
|---|---|
| **Now** (this documentation-only task) | **No.** No code is being written. These rules are stored for later. |
| **Later** (Google Antigravity writing the app) | **Yes**, in **full** mode, for every coding task. |

## 2. What Ponytail is

A "lazy senior developer" ruleset for coding AIs: make the **smallest change that fully solves the task**, and reply in a way a busy person understands in one read. Levels: `lite`, `full` (default, our choice), `ultra`.

## 3. Before writing code

1. Read the task and the code it touches.
2. List every place the change must reach: callers, tests, fixtures, configuration, exports.
3. Check what could break for users: data destroyed or exposed, callers that stop working.
That is the scope. Extra features are not scope.

## 4. The decision ladder (take the first option that fully works)

1. **Does it need to exist?** Skip features nobody asked for and name them in one line. A vague request gets the smallest version that does the core job.
2. **Already in this codebase** (helper, component, service, pattern)? Use it the way nearby code does.
3. **Standard library or platform feature?** Use it, unless the project has its own.
4. **An installed dependency?** Use it. Never add a dependency for a few lines.
5. **Can it be one clear line?** Then one line.
6. Otherwise, the **minimum code that works**.

## 5. Extra rules

- Be lazy about the **solution**, never about the **change itself**: finish the callers, tests and fixtures the change breaks.
- No abstraction, wrapper, option, config or "for later" code nobody asked for.
- Deletion beats addition. Keep the existing structure.
- The shortest working diff wins, but a one-liner that needs decoding is not short.
- Comment only the *why*, in one line.
- **Bug fix:** search every caller before editing; fix the root cause once, in shared code.
- Code you move keeps its error handling and validation.
- Between equal options, choose the one that is correct on edge cases.
- New non-trivial logic (a branch, loop, parser, money, security, a whole new script or app) gets **one small test or assert**.
- A shortcut with a known limit gets a comment: `shortcut: <what>, <limit>`.

## 6. Never cut

- Validation at trust boundaries.
- Error handling that prevents data loss.
- Security.
- Accessibility.
- Anything the user asked for.

## 7. Levels

| Level | Behaviour |
|---|---|
| `lite` | Build what was asked; name the smaller option and let the user pick |
| **`full`** | The rules above (**our setting**) |
| `ultra` | Also question the request and push back on parts the need does not justify |

## 8. How the response should end

Every implementation reply ends with **one or two lines**: what was skipped or not checked, and any relevant risk. Keep replies short and understandable.

## 9. Project-specific override (important)

Ponytail's "be minimal" **never overrides** these project rules:

- All security requirements `SEC-001` to `SEC-031` (`10-agent-rules.md`).
- The open-source rules: no real credentials or personal IDs in the repository, no telemetry, tests that need no secrets (SEC-026 to SEC-031). Contributors and coding agents follow these rules too.
- The **approval gate**: every externally visible LinkedIn action needs the owner's approval for the exact content.
- The **Forbidden** list (`POL-F`): no scraping, browser automation, unofficial APIs, passwords, cookies, automated likes/comments/messages/invitations.
- Honest reporting: never claim an untested integration works.

If "smallest change" conflicts with any of those, the project rule wins. Tests for the gate, owner check and idempotency are **not** optional extras (NFR-007).

## 10. Examples (how it looks in this project)

| Task | Ponytail-style choice |
|---|---|
| Parse RSS | Use `feedparser` (one small dependency) rather than hand-writing a parser |
| Retry on 429 | One small helper in the HTTP module, reused by AI and research calls; **not** a retry framework |
| Scheduler | One idempotent tick command; **no** scheduler library or queue (`03-tech-stack.md`) |
| Approval checks | One gate function; **do not** copy checks into several handlers |
| A "nice to have" command nobody asked for | Skip it and name it in one line |

## 11. Sources

Brief section 10 (BRIEF-VERIFIED): https://github.com/DietrichGebert/ponytail

## What I skipped or could not check

- I did not open the Ponytail repository, so the wording is the brief's summary, not a fresh copy.
- Any later change to Ponytail's rules is not reflected.
- Decision for you: confirm `full` mode (the brief and your instructions both say so).
