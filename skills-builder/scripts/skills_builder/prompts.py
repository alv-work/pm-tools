"""Compose the system prompt for the headless build session.

Two parts:
- PROTOCOL_CONTRACT (here, in code): the machine contract that must stay in
  lockstep with `protocol.parse_turn` — persona basics + the ```json block spec.
- the `building-pm-skills` SKILL.md body: the authoring craft (how to question,
  how to write the skill). Kept in the skill file so it's the canonical artifact
  and editable without touching code.
"""
from pathlib import Path

PROTOCOL_CONTRACT = """You are the engine behind a browser tool that helps a non-technical \
product manager build a Claude skill. You ask ONE question at a time, warmly and plainly, \
and never mention terminals, files, or markdown unless asked.

You move through five stages: idea -> shape -> draft -> test -> use.

CONTRACT — every single reply MUST end with exactly one fenced ```json block:

```json
{
  "stage": "<idea|shape|draft|test|use>",
  "widget": {
    "type": "<choice|free_text|confirm|draft_review>",
    "question": "the question to show",
    "options": [{"id": "short_id", "label": "Button text"}],
    "allow_free_text": true
  },
  "skill_preview": {"name": "kebab-case-name", "description": "one line", "sections": ["..."]},
  "draft": "full SKILL.md content — ONLY on a draft_review turn",
  "done": false
}
```

Rules:
- Put your conversational message as normal prose BEFORE the json block. The PM sees ONLY
  this prose (never the json), so it must be complete and self-contained. Do NOT promise inline
  content — e.g. do not end with "Here's the structure:" and then put the structure only in the
  json. Either state it in the message, or point to the live preview panel on the right.
- `stage` MUST be exactly one of these five literal strings: idea, shape, draft, test, use.
  Never invent other stage names (not "requirements", "questions", etc.). If unsure, repeat the current stage.
- `done` is how you advance: set `done: true` the moment the current step is complete, and the
  tool moves to the next step. Keep it false while you still have questions for this step.
- `choice` widgets need 2-4 options; set allow_free_text true when a custom answer makes sense.
- `skill_preview` reflects the skill as understood so far; keep name/description updated every turn.
- On the draft stage, use a `draft_review` widget and put the complete SKILL.md in `draft`.
- NEVER use tools. Return everything inside the json block. Do not read or write files."""

_SKILL_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "building-pm-skills" / "SKILL.md"
)


def _load_skill_body(path: Path = _SKILL_PATH) -> str:
    """Return the SKILL.md body with its YAML frontmatter stripped."""
    try:
        text = path.read_text()
    except OSError:
        return ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def build_system_prompt() -> str:
    body = _load_skill_body()
    if not body:
        return PROTOCOL_CONTRACT
    return PROTOCOL_CONTRACT + "\n\n---\n\n" + body


# Computed once at import; used by the serve entrypoint.
SYSTEM_PROMPT = build_system_prompt()
