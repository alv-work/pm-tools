"""Run the draft skill in a real, fresh claude session for the Test stage.

We spawn `claude -p` with cwd set to the build directory, so the draft at
`.claude/skills/<name>/SKILL.md` is discovered as a *project* skill — the exact
mechanism real sessions use, sandboxed per build with no global pollution.
Activation is inferred from a Skill tool call naming our skill. Denied tool calls
(the headless session cannot answer permission prompts) are surfaced as info.
"""
import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .claude_cli import run_claude
from .stream import parse_stream


@dataclass
class PlaygroundResult:
    reply: str
    activated: bool
    denied_tools: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    is_error: bool = False
    error_text: Optional[str] = None


class Playground:
    def __init__(self, cli: Callable = run_claude, timeout: int = 180):
        self._cli = cli
        self._timeout = timeout

    def run(self, build_dir, skill_name, message, session_id=None) -> PlaygroundResult:
        result = self._cli(
            message,
            cwd=str(build_dir),
            resume=session_id,
            timeout=self._timeout,
        )
        stream = parse_stream(result.lines)
        return PlaygroundResult(
            reply=stream.text,
            activated=_detect_activation(stream.tool_uses, skill_name),
            denied_tools=[d.get("tool_name") for d in stream.permission_denials if d.get("tool_name")],
            session_id=stream.session_id or session_id,
            is_error=stream.is_error or result.timed_out,
            error_text=stream.error_text or ("timed out" if result.timed_out else None),
        )


def _detect_activation(tool_uses, skill_name) -> bool:
    for t in tool_uses:
        if t.get("name") == "Skill" and skill_name in json.dumps(t.get("input") or {}):
            return True
    return False
