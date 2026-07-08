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


def _shape_turn(name="launch-announcements", draft=None, stage="shape", done=False):
    return Turn(
        chat_text="Who is the audience?",
        stage=stage,
        widget=Widget(type="choice", question="Who is the audience?",
                      options=[{"id": "internal", "label": "Internal teams"}],
                      allow_free_text=True),
        skill_preview={"name": name, "description": "Draft launch posts", "sections": []},
        draft=draft,
        done=done,
    )


def _app(engine, tmp_path, ids=("b1",), playground=None, installer=None):
    store = Store(root=tmp_path)
    idq = list(ids)
    return App(store=store, engine=engine,
               clock=lambda: "2026-07-08T00:00:00Z",
               id_gen=lambda: idq.pop(0), playground=playground,
               installer=installer), store


class FakeInstaller:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    def install(self, src, name, provenance, overwrite=False):
        self.calls.append({"name": name, "overwrite": overwrite, "provenance": provenance})
        if self._error:
            raise self._error
        return self._result


class FakePlayground:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def run(self, build_dir, skill_name, message, session_id=None):
        self.calls.append({"build_dir": str(build_dir), "skill_name": skill_name,
                           "message": message, "session_id": session_id})
        return self._result


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


def test_unknown_stage_does_not_crash_and_keeps_stage(tmp_path):
    # regression: a model turn with an invented stage (parsed to None) must not 422
    turns = [
        EngineResult(turn=_shape_turn(), session_id="s-1"),                    # idea -> shape
        EngineResult(turn=_shape_turn(stage=None), session_id="s-1"),          # bad stage, stays shape
    ]
    app, store = _app(FakeEngine(turns), tmp_path)
    app.create_build({})
    app.post_message("b1", {"text": "an idea"})
    status, body = app.post_message("b1", {"text": "external customers"})
    assert status == 200
    assert store.load("b1").stage == "shape"


def test_done_advances_to_next_stage(tmp_path):
    turns = [
        EngineResult(turn=_shape_turn(), session_id="s-1"),                    # idea -> shape
        EngineResult(turn=_shape_turn(stage=None, done=True), session_id="s-1"),  # done -> draft
    ]
    app, store = _app(FakeEngine(turns), tmp_path)
    app.create_build({})
    app.post_message("b1", {"text": "an idea"})
    app.post_message("b1", {"text": "external customers"})
    assert store.load("b1").stage == "draft"


def test_first_message_auto_advances_idea_to_shape(tmp_path):
    # even if the model keeps proposing stage "idea", giving the idea moves to shape
    eng = FakeEngine([EngineResult(turn=_shape_turn(stage="idea"), session_id="s-1")])
    app, store = _app(eng, tmp_path)
    app.create_build({})
    app.post_message("b1", {"text": "an idea"})
    assert store.load("b1").stage == "shape"


def test_test_message_runs_playground_and_returns_activation(tmp_path):
    from skills_builder.playground import PlaygroundResult
    pg = FakePlayground(PlaygroundResult(
        reply="Here's your post.", activated=True, denied_tools=["Bash"], session_id="pg-1"))
    eng = FakeEngine([EngineResult(turn=_shape_turn(), session_id="s-1")])
    app, store = _app(eng, tmp_path, playground=pg)
    app.create_build({})
    app.post_message("b1", {"text": "hi"})          # sets skill_name
    status, body = app.post_test_message("b1", {"text": "Draft a post"})
    assert status == 200
    assert body["activated"] is True
    assert body["reply"] == "Here's your post."
    assert body["denied_tools"] == ["Bash"]
    # playground got the build dir and skill name; session persisted
    assert pg.calls[0]["skill_name"] == "launch-announcements"
    assert store.load("b1").test_session_id == "pg-1"


def test_test_message_without_draft_is_400(tmp_path):
    pg = FakePlayground(None)
    app, _ = _app(FakeEngine([]), tmp_path, playground=pg)
    app.create_build({})
    status, body = app.post_test_message("b1", {"text": "hi"})
    assert status == 400
    assert body["error"]["kind"] == "no_draft"


def test_install_marks_installed_and_advances_to_use(tmp_path):
    from skills_builder.installer import InstallResult
    inst = FakeInstaller(result=InstallResult(name="launch-announcements",
                                              path="/skills/launch-announcements", overwritten=False))
    eng = FakeEngine([EngineResult(turn=_shape_turn(), session_id="s-1")])
    app, store = _app(eng, tmp_path, installer=inst)
    app.create_build({})
    app.post_message("b1", {"text": "hi"})    # sets skill_name
    meta = store.load("b1"); meta.stage = "test"; store.save(meta)  # at Test, ready to install
    status, body = app.post_install("b1", {})
    assert status == 200
    assert body["installed"]["name"] == "launch-announcements"
    reloaded = store.load("b1")
    assert reloaded.status == "installed"
    assert reloaded.stage == "use"
    assert inst.calls[0]["provenance"]["build_id"] == "b1"


def test_install_collision_returns_409(tmp_path):
    from skills_builder.installer import InstallError
    inst = FakeInstaller(error=InstallError("A skill named 'x' is already installed."))
    eng = FakeEngine([EngineResult(turn=_shape_turn(), session_id="s-1")])
    app, _ = _app(eng, tmp_path, installer=inst)
    app.create_build({})
    app.post_message("b1", {"text": "hi"})
    status, body = app.post_install("b1", {})
    assert status == 409
    assert body["error"]["kind"] == "collision"


def test_share_marks_shared_and_returns_mode(tmp_path):
    from skills_builder.sharer import ShareResult
    calls = {}

    def sharer(skill_dir, name):
        calls["name"] = name
        return ShareResult(mode="pr", url="https://x/pull/1")

    eng = FakeEngine([EngineResult(turn=_shape_turn(), session_id="s-1")])
    store = Store(root=tmp_path)
    app = App(store=store, engine=eng, clock=lambda: "t", id_gen=lambda: "b1", sharer=sharer)
    app.create_build({})
    app.post_message("b1", {"text": "hi"})
    status, body = app.post_share("b1", {})
    assert status == 200
    assert body["mode"] == "pr"
    assert body["url"] == "https://x/pull/1"
    assert store.load("b1").status == "shared"
    assert calls["name"] == "launch-announcements"
