# skills-builder — How to use

`skills-builder` is a browser tool that lets you build a Claude skill by
answering a few questions — no terminal, no files, no markdown. It asks what you
want Claude to do better, writes the skill for you, lets you test it in a real
sandbox, and installs it with one click.

Underneath, a local server drives a headless Claude session for both building and
testing. Everything runs on your machine; nothing is uploaded.

---

## 1. Prerequisites

- **Python 3.10+** (`python3 --version`). Standard library only — no pip installs.
- The **`claude` CLI**, installed and logged in. The Claude Code desktop app
  provides it. If you have never run it, open a terminal, run `claude` once, and
  sign in.
- macOS (first-class target; other platforms may work but are untested).

---

## 2. Install

From any Claude Code session:

```
/plugin marketplace add alv-work/pm-tools
/plugin install skills-builder@pm-tools
```

Reload plugins if prompted. You now have the `/skills-builder` command.

---

## 3. Launch

Run the command once:

```
/skills-builder
```

It starts a local server, opens your browser, and prints a `server-started` line
with a URL as a fallback. Once the browser is open you can close the desktop app —
the builder keeps running on its own local server until you stop it (Ctrl-C in the
terminal that launched it, or close that terminal).

The URL contains a one-time session key; only your machine can reach it
(`127.0.0.1`) and only with that key.

---

## 4. Build a skill

You move through five steps, shown on the left rail:

1. **Idea** — say what you want Claude to do better (e.g. "help me write launch
   announcements").
2. **Shape** — answer a few one-at-a-time questions (audience, when it should kick
   in, what a great result looks like). The right panel shows the skill taking
   shape.
3. **Draft** — the builder writes the skill. Read the friendly summary, or flip to
   the raw markdown. Ask for changes in plain language.
4. **Test** — the right panel becomes a live chat with a fresh Claude that has your
   draft loaded. A badge tells you whether the skill **activated**. If something's
   off, hit **Revise** to go back to Draft with your feedback.
5. **Use** — click **Install**. The skill lands in `~/.claude/skills/` and works in
   every future Claude session.

Unfinished builds appear on the **My Skills** home screen and resume where you
left off.

---

## 5. Share (optional)

On the Use step, **Share to team**:

- If you set `SKILLS_BUILDER_SHARE_REPO` to a local clone of your team's
  marketplace repo (and have `git` + `gh` working), it commits the skill to a
  branch and opens a pull request.
- Otherwise it **exports** a zip to `~/Downloads` with install instructions a
  teammate can follow.

Optional env vars:

- `SKILLS_BUILDER_SHARE_REPO` — path to the local marketplace clone.
- `SKILLS_BUILDER_SHARE_SUBDIR` — subfolder to place shared skills in (default
  `shared-skills`).

---

## 6. Where things live

- Builds (in progress and finished): `~/.claude/skills-builder/builds/<id>/` —
  `meta.json`, `transcript.jsonl`, and the draft skill tree. Human-readable;
  survives crashes, sleeps, and closed browsers.
- Installed skills: `~/.claude/skills/<name>/`, each with a `.skills-builder.json`
  provenance marker (build id, date, tool version).

---

## 7. Troubleshooting

- **"claude not found / not logged in"** — open a terminal, run `claude` once to
  sign in, then run `/skills-builder` again.
- **Browser didn't open** — copy the `url` from the `server-started` line into
  your browser.
- **A turn failed** — the builder shows a card with a "Try again" button; your
  conversation is never lost. Timeouts and CLI errors are retryable.
- **Name already installed** — on install you'll be offered **Overwrite** or
  **Rename & install**.
