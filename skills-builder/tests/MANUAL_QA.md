# skills-builder — manual QA & live smoke

The automated suite (`pytest skills-builder/tests`) covers the engine, protocol,
store, flow, server routing, playground, installer, and sharer with zero API cost
(a fake `claude` executable replays canned stream-json). Run it before every
change.

Two things automation can't cover: the real `claude` CLI and the browser UI. Run
these by hand before a release.

## Live smoke (real claude, ~2 turns of cost)

1. **Build turn parses.** From the repo root:
   ```
   PYTHONPATH=skills-builder/scripts python3 -c "from skills_builder.engine import Engine; from skills_builder.prompts import SYSTEM_PROMPT; import json; t=Engine(system_prompt=SYSTEM_PROMPT,timeout=180).turn('I want Claude to help write launch posts').turn; print(t.stage, t.widget and t.widget.type)"
   ```
   Expect a valid stage + widget type printed (no exception).

2. **Playground activation.** Write a small skill to a temp `.claude/skills/<name>/SKILL.md`,
   then `Playground(timeout=180).run(<tmp>, "<name>", "<a prompt that should trigger it>")`.
   Expect `activated True` and a sensible reply.

## Browser QA checklist

Launch with `/skills-builder` (or `python3 -m skills_builder serve`).

- [ ] Home shows "My Skills" and "Build a new skill".
- [ ] New build starts at **Idea**; the intro bubble appears.
- [ ] **Shape**: questions arrive one at a time; choice buttons and free text both work; the right panel updates the skill name/description.
- [ ] **Draft**: friendly view renders; Markdown toggle shows the raw SKILL.md.
- [ ] Asking for a change in plain language updates the draft.
- [ ] **Test**: the playground replies; the activation badge is correct; "Something's off → Revise" returns to Draft.
- [ ] **Use**: Install lands the skill in `~/.claude/skills/`; a name collision offers Overwrite / Rename.
- [ ] Share to team opens a PR (with `SKILLS_BUILDER_SHARE_REPO` set) or exports a zip to `~/Downloads`.
- [ ] Closing the browser and reopening the URL resumes an in-progress build.
- [ ] A forced error (e.g. log out of `claude`) shows a readable card with "Try again", not a stack trace.
