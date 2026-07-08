import pytest
from skills_builder.protocol import parse_turn, Turn, Widget, ProtocolError

VALID = """Here's my question for you.

```json
{
  "stage": "shape",
  "widget": {
    "type": "choice",
    "question": "Who is the audience?",
    "options": [{"id": "internal", "label": "Internal teams"}, {"id": "cust", "label": "Customers"}],
    "allow_free_text": true
  },
  "skill_preview": {"name": "launch-announcements", "description": "Draft launch posts", "sections": ["Overview"]},
  "done": false
}
```"""


def test_parses_chat_text_and_widget():
    t = parse_turn(VALID)
    assert isinstance(t, Turn)
    assert t.chat_text == "Here's my question for you."
    assert t.stage == "shape"
    assert isinstance(t.widget, Widget)
    assert t.widget.type == "choice"
    assert t.widget.allow_free_text is True
    assert [o["id"] for o in t.widget.options] == ["internal", "cust"]
    assert t.skill_preview["name"] == "launch-announcements"
    assert t.done is False


def test_missing_json_block_raises():
    with pytest.raises(ProtocolError):
        parse_turn("just some prose, no block")


def test_empty_turn_raises():
    with pytest.raises(ProtocolError):
        parse_turn("   ")


def test_malformed_json_raises():
    with pytest.raises(ProtocolError):
        parse_turn("text\n```json\n{not valid,}\n```")


def test_bad_stage_raises():
    with pytest.raises(ProtocolError):
        parse_turn('```json\n{"stage": "bogus"}\n```')


def test_bad_widget_type_raises():
    bad = '```json\n{"stage": "shape", "widget": {"type": "slider"}}\n```'
    with pytest.raises(ProtocolError):
        parse_turn(bad)


def test_option_missing_label_raises():
    bad = '```json\n{"stage": "shape", "widget": {"type": "choice", "options": [{"id": "x"}]}}\n```'
    with pytest.raises(ProtocolError):
        parse_turn(bad)


def test_widget_optional_on_done_turn():
    t = parse_turn('All set!\n```json\n{"stage": "use", "done": true}\n```')
    assert t.widget is None
    assert t.done is True
    assert t.chat_text == "All set!"


def test_draft_review_carries_draft_content():
    turn_text = (
        "Here's the draft.\n```json\n"
        '{"stage": "draft", "widget": {"type": "draft_review", "question": "Look good?"}, '
        '"draft": "---\\nname: x\\n---\\nbody"}\n```'
    )
    t = parse_turn(turn_text)
    assert t.widget.type == "draft_review"
    assert t.draft == "---\nname: x\n---\nbody"


def test_uses_last_json_block_when_prose_has_earlier_fence():
    turn_text = (
        "Example config:\n```json\n{\"unrelated\": 1}\n```\n"
        "Now my turn:\n```json\n{\"stage\": \"idea\", \"done\": false}\n```"
    )
    t = parse_turn(turn_text)
    assert t.stage == "idea"
