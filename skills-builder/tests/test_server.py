import pytest
from skills_builder.protocol import Turn, Widget
from skills_builder.engine import EngineResult, EngineError
from skills_builder.store import Store
from skills_builder.server import App


class FakeEngine:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def turn(self, prompt, *, session_id=None, cwd=None):
        self.calls.append({"prompt": prompt, "session_id": session_id})
        r = self._results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _shape_turn(name="launch-announcements", draft=None):
    return Turn(
        chat_text="Who is the audience?",
        stage="shape",
        widget=Widget(type="choice", question="Who is the audience?",
                      options=[{"id": "internal", "label": "Internal teams"}],
                      allow_free_text=True),
        skill_preview={"name": name, "description": "Draft launch posts", "sections": []},
        draft=draft,
        done=False,
    )


def _app(engine, tmp_path, ids=("b1",)):
    store = Store(root=tmp_path)
    idq = list(ids)
    return App(store=store, engine=engine,
               clock=lambda: "2026-07-08T00:00:00Z",
               id_gen=lambda: idq.pop(0)), store


def test_create_build_starts_at_idea(tmp_path):
    app, _ = _app(FakeEngine([]), tmp_path)
    status, body = app.create_build({"title": "Launch posts"})
    assert status == 201
    assert body["build"]["stage"] == "idea"
    assert body["build"]["id"] == "b1"


def test_get_build_returns_meta_and_transcript(tmp_path):
    app, _ = _app(FakeEngine([]), tmp_path)
    app.create_build({})
    status, body = app.get_build("b1")
    assert status == 200
    assert body["build"]["id"] == "b1"
    assert body["transcript"] == []


def test_post_message_advances_stage_and_persists_session(tmp_path):
    eng = FakeEngine([EngineResult(turn=_shape_turn(), session_id="s-1")])
    app, store = _app(eng, tmp_path)
    app.create_build({})
    status, body = app.post_message("b1", {"text": "help with launch posts"})
    assert status == 200
    assert body["turn"]["stage"] == "shape"
    assert body["turn"]["widget"]["type"] == "choice"
    meta = store.load("b1")
    assert meta.stage == "shape"
    assert meta.session_id == "s-1"
    assert meta.skill_name == "launch-announcements"
    # transcript recorded both sides
    assert [e["role"] for e in store.read_transcript("b1")] == ["user", "assistant"]


def test_choice_id_resolves_to_label_in_prompt(tmp_path):
    eng = FakeEngine([
        EngineResult(turn=_shape_turn(), session_id="s-1"),
        EngineResult(turn=_shape_turn(), session_id="s-1"),
    ])
    app, _ = _app(eng, tmp_path)
    app.create_build({})
    app.post_message("b1", {"text": "launch posts"})   # produces a widget with 'internal'
    app.post_message("b1", {"choice_id": "internal"})
    assert "Internal teams" in eng.calls[1]["prompt"]


def test_engine_timeout_maps_to_504_error_card(tmp_path):
    eng = FakeEngine([EngineError("slow", kind="timeout")])
    app, _ = _app(eng, tmp_path)
    app.create_build({})
    status, body = app.post_message("b1", {"text": "hi"})
    assert status == 504
    assert body["error"]["kind"] == "timeout"


def test_draft_content_is_written_to_disk(tmp_path):
    turn = _shape_turn(draft="---\nname: launch-announcements\n---\nbody")
    eng = FakeEngine([EngineResult(turn=turn, session_id="s-1")])
    app, store = _app(eng, tmp_path)
    app.create_build({})
    app.post_message("b1", {"text": "hi"})
    assert store.draft_path("b1", "launch-announcements").exists()


def test_post_to_missing_build_is_404(tmp_path):
    app, _ = _app(FakeEngine([]), tmp_path)
    status, body = app.post_message("nope", {"text": "hi"})
    assert status == 404
