import json
from skills_builder.stream import parse_stream, StreamResult


def _lines(*events):
    return [json.dumps(e) for e in events]


SUCCESS = _lines(
    {"type": "system", "subtype": "hook_started", "hook_name": "SessionStart"},
    {"type": "system", "subtype": "init", "session_id": "sess-1", "tools": ["Read"]},
    {"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 42},
    {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "hmm"}]}},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello there"}]}},
    {"type": "result", "subtype": "success", "is_error": False,
     "result": "Hello there", "session_id": "sess-1"},
)


def test_extracts_text_and_session_id():
    r = parse_stream(SUCCESS)
    assert isinstance(r, StreamResult)
    assert r.text == "Hello there"
    assert r.session_id == "sess-1"
    assert r.is_error is False


def test_ignores_hook_and_thinking_noise_and_bad_lines():
    lines = ["not json at all", ""] + SUCCESS
    r = parse_stream(lines)
    assert r.text == "Hello there"


def test_collects_tool_uses():
    lines = _lines(
        {"type": "system", "subtype": "init", "session_id": "s"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "launch-announcements"}},
        ]}},
        {"type": "result", "subtype": "success", "is_error": False, "result": "done", "session_id": "s"},
    )
    r = parse_stream(lines)
    assert r.tool_names == ["Skill"]
    assert r.tool_uses[0]["input"]["skill"] == "launch-announcements"


def test_result_is_error_flags_error():
    lines = _lines(
        {"type": "system", "subtype": "init", "session_id": "s"},
        {"type": "result", "subtype": "error_during_execution", "is_error": True,
         "result": "boom", "session_id": "s"},
    )
    r = parse_stream(lines)
    assert r.is_error is True
    assert r.error_text == "boom"


def test_no_result_event_is_treated_as_error():
    lines = _lines(
        {"type": "system", "subtype": "init", "session_id": "s"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "partial"}]}},
    )
    r = parse_stream(lines)
    assert r.is_error is True
    assert "without a result" in r.error_text


def test_falls_back_to_assistant_text_when_result_text_missing():
    lines = _lines(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "part A "}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "part B"}]}},
        {"type": "result", "subtype": "success", "is_error": False, "session_id": "s"},
    )
    r = parse_stream(lines)
    assert r.text == "part A part B"
