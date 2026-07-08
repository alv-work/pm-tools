"""Drive one build-conversation turn through the headless claude session.

The engine is the seam between deterministic server code and the model: it calls
the CLI, parses the stream, validates the protocol block, and — per the spec —
performs exactly one automatic corrective retry when the JSON block is missing or
malformed. Every failure it raises is a typed `EngineError` the server turns into
a PM-readable card; stack traces never propagate to the UI.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from .claude_cli import run_claude
from .protocol import Turn, parse_turn, ProtocolError
from .stream import parse_stream, StreamResult

CORRECTIVE_PROMPT = (
    "Your previous message did not end with a valid ```json protocol block. "
    "Send the turn again, ending with exactly one ```json block that matches the "
    "contract (stage, optional widget, optional skill_preview, done). "
    "Do not add commentary about the mistake."
)

# The build conversation never needs tools — the model returns everything (including
# draft SKILL.md content) inside the protocol JSON. Denying tools keeps the headless
# session from stalling on a permission prompt it cannot answer.
_BUILD_DISALLOWED_TOOLS = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]


class EngineError(Exception):
    def __init__(self, message, kind="unknown", detail=None):
        super().__init__(message)
        self.kind = kind        # setup | timeout | crash | protocol
        self.detail = detail


@dataclass
class EngineResult:
    turn: Turn
    session_id: Optional[str]


class Engine:
    def __init__(
        self,
        cli: Callable = run_claude,
        *,
        corrective_prompt: str = CORRECTIVE_PROMPT,
        system_prompt: Optional[str] = None,
        timeout: int = 120,
        disallowed_tools=None,
    ):
        self._cli = cli
        self._corrective = corrective_prompt
        self._system_prompt = system_prompt
        self._timeout = timeout
        self._disallowed_tools = (
            _BUILD_DISALLOWED_TOOLS if disallowed_tools is None else disallowed_tools
        )

    def turn(self, prompt: str, *, session_id: Optional[str] = None, cwd: Optional[str] = None) -> EngineResult:
        stream = self._call(prompt, resume=session_id, cwd=cwd)
        sid = stream.session_id or session_id
        try:
            return EngineResult(parse_turn(stream.text), sid)
        except ProtocolError:
            stream2 = self._call(self._corrective, resume=sid, cwd=cwd)
            sid = stream2.session_id or sid
            try:
                return EngineResult(parse_turn(stream2.text), sid)
            except ProtocolError as e:
                raise EngineError(
                    "Claude's reply didn't match the expected format.",
                    kind="protocol", detail=str(e),
                )

    def _call(self, prompt, *, resume, cwd) -> StreamResult:
        result = self._cli(
            prompt,
            resume=resume,
            cwd=cwd,
            timeout=self._timeout,
            system_prompt=self._system_prompt,
            disallowed_tools=self._disallowed_tools,
        )
        if result.timed_out:
            raise EngineError("Claude took too long to respond.", kind="timeout",
                              detail=result.stderr)
        stream = parse_stream(result.lines)
        if result.returncode != 0 and not stream.text:
            raise EngineError("The Claude CLI exited with an error.", kind="crash",
                              detail=(result.stderr or "")[-2000:])
        if stream.is_error:
            raise EngineError("Claude reported an error.", kind="crash",
                              detail=stream.error_text)
        return stream
