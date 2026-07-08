"""Parse `claude -p --output-format stream-json` output into a compact result.

The real stream is noisy: SessionStart hooks, `thinking_tokens` counters, and
multiple `assistant` events precede the payload. We keep only what the engine
needs — the final assistant text, tool calls, session id, and error state — and
skip everything else (including non-JSON lines) defensively.
"""
import json
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass
class StreamResult:
    text: str
    tool_uses: list          # list[dict]: {"name": str, "input": dict}
    session_id: Optional[str]
    is_error: bool
    error_text: Optional[str]

    @property
    def tool_names(self):
        return [t["name"] for t in self.tool_uses]


def parse_stream(lines: Iterable[str]) -> StreamResult:
    session_id = None
    tool_uses = []
    assistant_text_parts = []
    result_text = None
    is_error = False
    error_text = None
    saw_result = False

    for line in lines:
        if not isinstance(line, str):
            continue
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(evt, dict):
            continue

        etype = evt.get("type")
        if etype == "system":
            if evt.get("subtype") == "init" and evt.get("session_id"):
                session_id = evt["session_id"]
        elif etype == "assistant":
            msg = evt.get("message") or {}
            for block in msg.get("content") or []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    assistant_text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_uses.append({
                        "name": block.get("name", ""),
                        "input": block.get("input") or {},
                    })
        elif etype == "result":
            saw_result = True
            if evt.get("session_id"):
                session_id = evt["session_id"]
            is_error = bool(evt.get("is_error", False))
            res = evt.get("result")
            if isinstance(res, str):
                result_text = res
            if is_error:
                error_text = (
                    res if isinstance(res, str)
                    else evt.get("api_error_status") or "claude reported an error"
                )

    if not saw_result:
        is_error = True
        error_text = error_text or "claude ended without a result"

    text = result_text if result_text is not None else "".join(assistant_text_parts)
    return StreamResult(
        text=text,
        tool_uses=tool_uses,
        session_id=session_id,
        is_error=is_error,
        error_text=error_text,
    )
