"""Parse the fenced JSON contract block that ends every build-conversation turn.

Pure functions only — no I/O. The headless Claude session is instructed to end
each turn with one ```json block; this module turns that block into a `Turn`.
"""
import json
import re
from dataclasses import dataclass
from typing import Optional

STAGES = ("idea", "shape", "draft", "test", "use")
WIDGET_TYPES = ("choice", "free_text", "confirm", "draft_review")

_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)


class ProtocolError(Exception):
    """Raised when a turn's trailing JSON block is missing or malformed."""


@dataclass
class Widget:
    type: str
    question: str
    options: list          # list[dict]: {"id": str, "label": str}
    allow_free_text: bool


@dataclass
class Turn:
    chat_text: str
    stage: Optional[str]    # one of STAGES, or None if the model emitted an unknown value
    widget: Optional[Widget]
    skill_preview: dict     # {"name", "description", "sections"}
    draft: Optional[str]    # full SKILL.md content, present on draft_review
    done: bool


def parse_turn(text: str) -> Turn:
    """Extract and validate the last ```json block in `text`.

    The prose before the block becomes `chat_text` (the chat bubble).
    """
    if not text or not text.strip():
        raise ProtocolError("empty turn")
    matches = _FENCE_RE.findall(text)
    if not matches:
        raise ProtocolError("no ```json block found in turn")
    raw = matches[-1].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"turn JSON is not valid: {e}")
    if not isinstance(data, dict):
        raise ProtocolError("turn JSON must be an object")

    # `stage` is advisory: the server's flow machine is authoritative, so an
    # unknown value (models sometimes invent stage names) must not throw away an
    # otherwise-valid turn — it just means "no stage hint this turn".
    stage = data.get("stage")
    if stage not in STAGES:
        stage = None

    widget = _parse_widget(data.get("widget"))
    return Turn(
        chat_text=_strip_last_block(text),
        stage=stage,
        widget=widget,
        skill_preview=data.get("skill_preview") or {},
        draft=data.get("draft"),
        done=bool(data.get("done", False)),
    )


def _parse_widget(w) -> Optional[Widget]:
    if w is None:
        return None
    if not isinstance(w, dict):
        raise ProtocolError("widget must be an object")
    wtype = w.get("type")
    if wtype not in WIDGET_TYPES:
        raise ProtocolError(f"widget.type must be one of {WIDGET_TYPES}, got {wtype!r}")
    options = w.get("options") or []
    if not isinstance(options, list):
        raise ProtocolError("widget.options must be a list")
    norm = []
    for o in options:
        if not isinstance(o, dict) or "id" not in o or "label" not in o:
            raise ProtocolError("each widget option needs id and label")
        norm.append({"id": str(o["id"]), "label": str(o["label"])})
    return Widget(
        type=wtype,
        question=str(w.get("question", "")),
        options=norm,
        allow_free_text=bool(w.get("allow_free_text", False)),
    )


def _strip_last_block(text: str) -> str:
    """Return the prose before the final ```json block, trimmed."""
    last = None
    for last in _FENCE_RE.finditer(text):
        pass
    if last is None:
        return text.strip()
    return text[: last.start()].strip()
