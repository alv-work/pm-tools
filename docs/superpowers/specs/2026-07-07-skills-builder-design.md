# Skills Builder — Design

**Date:** 2026-07-07
**Status:** Approved pending final spec review
**Repo:** pm-tools, new `skills-builder/` plugin

## Purpose

A browser interface that lets PMs and other non-technical teammates build, test, install, and share Claude skills without touching a terminal. Underneath, it drives the `superpowers:brainstorming` questioning approach and `superpowers:writing-skills` authoring rules through headless Claude sessions.

## Goals

- A PM with the Claude Code desktop app and this plugin can go from idea to installed, working skill in one sitting, unassisted.
- Every skill is validated in a real playground session before install.
- Nothing in the flow exposes a terminal, file path, or raw markdown (unless the PM asks).

## Non-goals (v1)

- No hosted/multi-user service — strictly local, one machine, one PM.
- No skill-editing UI for skills not built by this tool.
- No automatic marketplace publishing — sharing is a PR (or zip export), reviewed by a human.
- No Windows support commitment (matches the rest of pm-tools; macOS first).

## Decisions made during brainstorming

| Decision | Choice |
|---|---|
| Runtime | Local pm-tools plugin + browser UI |
| Skill destination | Local install to `~/.claude/skills`, optional share to team repo |
| PM environment | Claude Code desktop app (used only to launch) |
| Skill validation | Built-in playground with real fresh sessions |
| Interaction model | Hybrid: journey rail + conversation center + live preview panel |
| Claude integration | Headless engine — server drives `claude -p` for build and playground |

## User journey

1. **Launch.** PM types `/skills-builder` in the desktop app. The command starts a local server, opens the browser, prints the URL as fallback. The desktop app can then be closed.
2. **Home.** "My Skills" gallery (drafts, installed, shared — with provenance) plus "Build a new skill". Unfinished builds resume.
3. **Build flow**, journey rail: **Idea → Shape → Draft → Test → Use**.
   - **Idea:** free-text "What do you want Claude to do better?" with example chips.
   - **Shape:** one-question-at-a-time conversation; multiple-choice buttons plus always-available free text. Right panel: skill summary forming live (name, description, trigger phrases).
   - **Draft:** engine writes the skill applying writing-skills quality rules. Right panel renders a friendly view ("When it activates", "What it does", examples); raw markdown behind a toggle. PM iterates in plain language.
   - **Test:** right panel becomes a playground chat backed by a real fresh session with the draft skill loaded. An "activated / didn't activate" badge on each exchange. "Something's off" returns to Draft carrying the feedback.
   - **Use:** one-click install; copyable starter prompt; optional "Share to team".

## Architecture

```
Browser (vanilla HTML/JS/CSS)
   ↕ HTTP + SSE, session-key gated, 127.0.0.1 only
server.py (Python stdlib) — owns all state, validates stage transitions
   ↕ subprocess
claude -p --output-format stream-json
   • build conversation: one persistent session, --resume per turn
   • playground: fresh session per Test run, cwd = build dir
```

The desktop app session only launches the server; it is not part of the loop.

## Components

```
skills-builder/
  commands/skills-builder.md        # slash command: start server, open browser
  scripts/
    server.py        # stdlib HTTP server: static UI, JSON API, SSE
    engine.py        # spawns/resumes claude -p, parses stream-json, enforces protocol
    flow.py          # build state machine: Idea→Shape→Draft→Test→Use
    playground.py    # fresh-session runner for Test
    installer.py     # install to ~/.claude/skills, share/export
    store.py         # build state under ~/.claude/skills-builder/builds/<id>/
    ui/              # static frontend (CDN fonts allowed, read-md precedent)
  skills/
    building-pm-skills/SKILL.md     # orchestrator skill for the headless build session
  tests/
```

- **server.py** routes; knows nothing Claude-specific.
- **engine.py** is the only module that talks to the `claude` CLI.
- **building-pm-skills** (skill) instructs the build session: question like `superpowers:brainstorming`, author like `superpowers:writing-skills`, skip developer-workflow steps (plans, TDD), target PM-grade skills, and end every turn with the protocol JSON block. Superpowers is a declared plugin dependency.
- **flow.py** validates every transition server-side; the model proposes, deterministic code disposes.
- **store.py** keeps everything on disk, human-readable; builds survive crashes, sleeps, closed browsers.

## Turn protocol

Every build-conversation turn from the headless session must end with one fenced JSON block:

```json
{
  "stage": "shape",
  "widget": {
    "type": "choice",
    "question": "Who is the audience?",
    "options": [{"id": "internal", "label": "Internal teams"}],
    "allow_free_text": true
  },
  "skill_preview": {"name": "launch-announcements", "description": "…", "sections": ["…"]},
  "done": false
}
```

`widget.type` ∈ `choice | free_text | confirm | draft_review`. `done: true` signals stage completion; the server (flow.py) decides whether to advance. Text before the block is the chat bubble. Malformed or missing JSON: server sends one corrective turn automatically; on second failure the UI shows a retry card. The transcript is never lost.

## HTTP API

All endpoints gated by a session key in the URL; server binds 127.0.0.1.

- `GET /api/builds`, `POST /api/builds` — list, start
- `GET /api/builds/<id>` — full state (used for resume)
- `POST /api/builds/<id>/message` — `{text}` or `{choice_id}`
- `GET /api/builds/<id>/stream` — SSE; phase 1: turn-complete events (spinner UX); phase 2: text deltas
- `POST /api/builds/<id>/test/message` — playground exchange
- `POST /api/builds/<id>/install`, `POST /api/builds/<id>/share`

## Playground mechanics

Draft skill is written to `~/.claude/skills-builder/builds/<id>/.claude/skills/<name>/SKILL.md`. The playground spawns `claude -p` with `cwd` set to the build dir, so the skill is discovered as a project skill — the same discovery path real sessions use, sandboxed per build, no global pollution. Skill activation is detected from tool calls in stream-json and shown as a badge per exchange. Headless sessions cannot answer permission prompts, so denied tool calls surface as an informational note ("in the real app Claude would ask permission here"), not an error.

## Install and share

- **Install:** copy to `~/.claude/skills/<name>/` plus a provenance marker file (build id, date, tool version). Name collision → UI offers rename or overwrite. Gallery supports uninstall/rebuild.
- **Share:** if `SKILLS_BUILDER_SHARE_REPO` is configured and `git`/`gh` are usable, "Share to team" commits the skill to a branch and opens a PR against the marketplace repo. Otherwise the button reads "Export" and produces a zip in `~/Downloads` with install instructions for a teammate.

## State and persistence

Per build, under `~/.claude/skills-builder/builds/<id>/`: `meta.json` (stage, session id, skill name, timestamps), `transcript.jsonl`, and the draft skill tree. User-level location (not project-level) because PMs have no meaningful cwd.

## Error handling

Every failure is a PM-readable card; stack traces never reach the UI.

- `claude` CLI missing or logged out → setup screen with one copyable fix command and a "check again" button.
- Malformed turn JSON → one automatic corrective retry, then a retry card.
- Hung turn (no output for 120s) → kill process, retry card; retry resumes the same session.
- `claude -p` nonzero exit → summarized stderr behind a "details" disclosure, retry button.
- Port in use → auto-pick a free port. Crash/sleep → resume from disk state.
- Playground tool denial → informational note (see Playground mechanics).

## Security

- Server binds 127.0.0.1 only; every request requires the per-launch session key (same model as the superpowers visual companion).
- No credentials stored; Claude auth is the PM's existing CLI login.

## Testing

- **Unit (pytest):** protocol parser (canned turns → widgets, malformed variants), flow transitions (illegal jumps rejected), store round-trips, installer against a temp HOME.
- **Integration:** a fake `claude` executable on PATH replaying canned stream-json drives engine.py end to end — deterministic, zero API cost. Same style as babysit-doc's tests.
- **Live smoke:** one manual-marked real one-turn build, run before releases.
- **UI:** logic kept in the API layer so contract tests cover it; manual QA checklist for the browser.

## Dependencies

- Python 3 stdlib only (repo rule).
- `claude` CLI installed and authenticated (desktop app install provides it).
- Superpowers plugin (for `superpowers:brainstorming`, `superpowers:writing-skills`) — declared dependency.
- `git`/`gh` optional, only for Share.

## Build phases

1. Engine + protocol parser + fake-claude tests (the risky core, proven first).
2. Server + store + flow with spinner-grade SSE; minimal UI through Shape.
3. Draft + preview panel.
4. Playground.
5. Install, gallery, resume.
6. Share/export, polish, error cards, live smoke test.
