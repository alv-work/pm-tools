# babysit-doc — Design

Date: 2026-07-02
Owner: Alabhya Vaibhav
Status: Approved for planning
Home: second plugin in the `pm-tools` marketplace (`alv-work/pm-tools`)

## Problem

Shared docs (specs, PRDs) accumulate comments, questions, and suggestions from
collaborators. Keeping up means repeatedly reopening the doc, reading every new
thread, and replying. A PM wants an agent that watches a doc on their behalf,
drafts replies to threads it understands, and nudges them with a ready-to-send
draft when it is unsure — without ever posting under their name unreviewed.

## Scope

**v1 (this spec):**
- Platform: **Confluence only** (Cloud REST API, API-token auth).
- Surface handled: **comment threads** (footer + inline comments) — questions,
  requests, and discussion.
- Autonomy: **draft-only**. Every reply is presented for human approval; nothing
  posts automatically.
- Review surface: **in the Claude Code session** (the pass prints a list of
  threads with drafted replies and per-item actions).
- Recurrence: **reuse the existing `/loop`** (e.g. `/loop 10m /babysit-doc <url>`);
  no custom scheduler.

**Explicitly deferred (v2+), and why none force a redesign:**
- MS Word / SharePoint via Microsoft Graph — a second `DocSource` implementation;
  the loop logic is platform-agnostic.
- Auto-post-when-confident — a config flag gating the existing `post_reply` step.
- Inline *suggestion* (tracked-edit accept/reject) handling — a new thread type.
- Slack / email delivery of nudges — an alternate review surface.

## Architecture

Small units with one job each, communicating through defined interfaces.

### `DocSource` (platform boundary)
Abstract interface so loop logic never knows the platform:
- `list_threads(doc_ref) -> [Thread]` — open comment threads on the doc.
- `get_context(thread) -> str` — the doc text the thread anchors to (for inline)
  or the surrounding section (for footer comments).
- `post_reply(thread, text) -> None` — post a reply into a thread.
- `resolve(thread) -> None` — optional; mark a thread resolved. May be a no-op in v1.

A `Thread` carries: stable `id`, author, created/updated timestamps, the comment
text (full reply chain), a permalink, and an `anchor` (inline selection or "footer").

v1 ships one implementation: **`ConfluenceSource`**.
- Auth: base URL + account email + API token (Confluence Cloud basic auth).
- Reads: inline + footer comments for a page (REST API, following reply chains).
- Writes: reply as a child comment in the thread.

### State store
Per-doc JSON at `~/.config/babysit-doc/state/<doc-id>.json`:
- `seen`: map of thread id → last-seen `updated` timestamp.
- `last_check`: ISO timestamp.
Purpose: each pass processes only **new or updated** threads and never re-drafts
a thread already handled. Threads updated since last seen (new replies) re-enter
the queue.

### Drafter (the Claude step)
For each queued thread: read comment + `get_context`, then decide and produce:
- `needs_reply`: is this addressed to us / does it warrant a response?
- `confidence`: `high` | `low` — is the answer well-supported by the doc/context?
- `draft`: proposed reply text.
- `rationale`: one line on why, and what it's unsure about when `low`.
`low`-confidence items are flagged "needs you" but still carry a draft to react to.

### Review surface (Claude-mediated, in-session)
The script does not block on interactive input. Instead the two-mode split below
lets **Claude** (driven by the command file) mediate approval in conversation:
1. `scan` mode emits the queued threads + drafts as **structured JSON** to stdout.
2. The command instructs Claude to present each: doc/thread permalink, author, the
   comment, a context snippet, the drafted reply, and the confidence flag — then
   ask the human to **approve**, **edit**, or **skip** per item.
3. For each approved/edited item, Claude calls the script in `post` mode with the
   thread id and final text.
Draft-only is enforced structurally: `scan` never posts; `post` only runs on an
item the human approved.

### Poster (`post` mode)
`DocSource.post_reply(thread, text)`, then record the thread as seen with its
current `updated` timestamp. A skipped thread is left unseen, so it resurfaces
next pass (until it changes or is handled). `scan` updates `last_check` only.

### Runner (command)
`/babysit-doc <page-url-or-id>` runs a **scan pass**, Claude presents drafts and
collects approvals, then issues `post` calls for approved items:
`resolve doc → list_threads → diff vs state → draft each new/updated → (scan JSON)
→ Claude surfaces → human approves → post approved → save state`. Continuous
watching is `/loop <interval> /babysit-doc <url>`.

## Data flow

```
/babysit-doc <url>
      │
      ▼
ConfluenceSource.list_threads ──► diff against state.seen ──► queue (new/updated)
      │                                                            │
      ▼                                                            ▼
   (nothing new → report "no new threads", exit)            Drafter per thread
                                                                   │
                                                                   ▼
                                              Review surface (approve / edit / skip)
                                                                   │
                                                       approve/edit ▼
                                                     ConfluenceSource.post_reply
                                                                   │
                                                                   ▼
                                                          update state.seen
```

## Configuration & auth

Resolved from env first, then `~/.config/babysit-doc/config.json`:
- `CONFLUENCE_BASE_URL` (e.g. `https://acme.atlassian.net/wiki`)
- `CONFLUENCE_EMAIL`
- `CONFLUENCE_API_TOKEN`

Missing/invalid credentials produce one clear error and abort the pass before any
doc access — no partial output.

## Error handling

- Auth failure → single clear message, exit non-zero.
- Doc ref unresolvable (bad URL / no access) → clear message naming the ref.
- API rate limit / transient 5xx → bounded retry with backoff; if still failing,
  report and exit.
- Per-thread drafting failure → skip that thread with a noted error; the rest of
  the pass continues (one bad thread never aborts the run).
- `post_reply` failure after approval → report which thread failed; that thread is
  NOT marked seen, so it can be retried next pass.

## Testing

- **Unit:** diff/state logic against a `FakeDocSource` with fixture threads —
  new-thread detection, updated-thread re-queue, seen-suppression, skip behavior.
- **Drafter harness:** recorded threads → assert confidence classification and that
  a draft is always produced; `low`-confidence items are flagged.
- **Integration (gated):** against a real Confluence test page behind an env flag —
  list, draft, post to a scratch thread, verify state written.

## Packaging

```
babysit-doc/
├── .claude-plugin/plugin.json
├── commands/babysit-doc.md          # runner; invokes the script
└── scripts/babysit_doc/             # Python package (stdlib + minimal deps)
    ├── __main__.py                  # entrypoint: `scan` and `post` subcommands
    ├── sources/base.py              # DocSource interface + Thread
    ├── sources/confluence.py        # ConfluenceSource
    ├── state.py                     # state store
    └── drafter.py                   # classify + draft
```
Add a `babysit-doc` entry to the repo's `.claude-plugin/marketplace.json`.
Install path: `/plugin install babysit-doc@pm-tools`.
