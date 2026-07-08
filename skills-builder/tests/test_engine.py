import json
import pytest
from skills_builder.claude_cli import CliResult
from skills_builder.engine import Engine, EngineError, EngineResult


def _stream(text, session_id="sess-1", is_error=False):
    events = [
        {"type": "system", "subtype": "init", "session_id": session_id},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
        {"type": "result", "subtype": "success", "is_error": is_error,
         "result": text, "session_id": session_id},
    ]
    return [json.dumps(e) for e in events]


VALID_TURN = 'Question?\n```json\n{"stage": "shape", "widget": {"type": "free_text", "question": "?"}}\n```'
BAD_TURN = "I forgot the json block entirely."


class ScriptedCli:
    """Returns queued CliResults; records each call's kwargs."""
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return self._results.pop(0)


def test_happy_path_returns_parsed_turn_and_session_id():
    cli = ScriptedCli([CliResult(lines=_stream(VALID_TURN, "s-abc"), returncode=0, stderr="")])
    eng = Engine(cli=cli)
    res = eng.turn("start building")
    assert isinstance(res, EngineResult)
    assert res.turn.stage == "shape"
    assert res.turn.widget.type == "free_text"
    assert res.session_id == "s-abc"


def test_malformed_turn_triggers_one_corrective_retry():
    cli = ScriptedCli([
        CliResult(lines=_stream(BAD_TURN, "s-1"), returncode=0, stderr=""),
        CliResult(lines=_stream(VALID_TURN, "s-1"), returncode=0, stderr=""),
    ])
    eng = Engine(cli=cli)
    res = eng.turn("hi")
    assert res.turn.stage == "shape"
    assert len(cli.calls) == 2
    # the corrective retry resumes the same session captured from turn 1
    assert cli.calls[1]["resume"] == "s-1"


def test_two_malformed_turns_raise_protocol_error():
    cli = ScriptedCli([
        CliResult(lines=_stream(BAD_TURN, "s-1"), returncode=0, stderr=""),
        CliResult(lines=_stream(BAD_TURN, "s-1"), returncode=0, stderr=""),
    ])
    eng = Engine(cli=cli)
    with pytest.raises(EngineError) as ei:
        eng.turn("hi")
    assert ei.value.kind == "protocol"


def test_timeout_raises_timeout_error():
    cli = ScriptedCli([CliResult(lines=[], returncode=-1, stderr="timed out", timed_out=True)])
    eng = Engine(cli=cli)
    with pytest.raises(EngineError) as ei:
        eng.turn("hi")
    assert ei.value.kind == "timeout"


def test_nonzero_exit_with_no_output_raises_crash():
    cli = ScriptedCli([CliResult(lines=[], returncode=1, stderr="not logged in")])
    eng = Engine(cli=cli)
    with pytest.raises(EngineError) as ei:
        eng.turn("hi")
    assert ei.value.kind == "crash"
    assert "not logged in" in (ei.value.detail or "")


def test_result_error_raises_crash():
    cli = ScriptedCli([CliResult(lines=_stream("boom", "s-1", is_error=True), returncode=0, stderr="")])
    eng = Engine(cli=cli)
    with pytest.raises(EngineError) as ei:
        eng.turn("hi")
    assert ei.value.kind == "crash"


def test_resume_passes_session_id_through():
    cli = ScriptedCli([CliResult(lines=_stream(VALID_TURN, "s-9"), returncode=0, stderr="")])
    eng = Engine(cli=cli)
    eng.turn("next", session_id="s-9")
    assert cli.calls[0]["resume"] == "s-9"
