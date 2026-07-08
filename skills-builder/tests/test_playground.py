import json
from skills_builder.claude_cli import CliResult
from skills_builder.playground import Playground, PlaygroundResult


def _stream(text, tool_uses=None, denials=None, session_id="pg-1"):
    events = [{"type": "system", "subtype": "init", "session_id": session_id}]
    for t in (tool_uses or []):
        events.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": t["name"], "input": t.get("input", {})}]}})
    events.append({"type": "result", "subtype": "success", "is_error": False,
                   "result": text, "session_id": session_id,
                   "permission_denials": denials or []})
    return [json.dumps(e) for e in events]


class ScriptedCli:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, message, **kwargs):
        self.calls.append({"message": message, **kwargs})
        return self._results.pop(0)


def test_detects_activation_when_skill_tool_names_our_skill():
    cli = ScriptedCli([CliResult(
        lines=_stream("Here's your announcement…",
                      tool_uses=[{"name": "Skill", "input": {"skill": "launch-announcements"}}]),
        returncode=0, stderr="")])
    pg = Playground(cli=cli)
    res = pg.run("/tmp/build", "launch-announcements", "Draft a post for feature X")
    assert isinstance(res, PlaygroundResult)
    assert res.activated is True
    assert res.reply.startswith("Here's your announcement")


def test_not_activated_when_skill_not_invoked():
    cli = ScriptedCli([CliResult(lines=_stream("Sure, here you go."), returncode=0, stderr="")])
    pg = Playground(cli=cli)
    res = pg.run("/tmp/build", "launch-announcements", "hi")
    assert res.activated is False


def test_not_activated_when_a_different_skill_runs():
    cli = ScriptedCli([CliResult(
        lines=_stream("...", tool_uses=[{"name": "Skill", "input": {"skill": "some-other"}}]),
        returncode=0, stderr="")])
    pg = Playground(cli=cli)
    assert pg.run("/tmp/build", "launch-announcements", "hi").activated is False


def test_surfaces_denied_tools():
    cli = ScriptedCli([CliResult(
        lines=_stream("...", denials=[{"tool_name": "Bash"}, {"tool_name": "WebFetch"}]),
        returncode=0, stderr="")])
    pg = Playground(cli=cli)
    res = pg.run("/tmp/build", "launch-announcements", "hi")
    assert res.denied_tools == ["Bash", "WebFetch"]


def test_runs_fresh_session_in_build_dir():
    cli = ScriptedCli([CliResult(lines=_stream("ok"), returncode=0, stderr="")])
    pg = Playground(cli=cli)
    pg.run("/tmp/build-42", "launch-announcements", "hi")
    assert cli.calls[0]["cwd"] == "/tmp/build-42"


def test_resume_threads_playground_session():
    cli = ScriptedCli([CliResult(lines=_stream("ok", session_id="pg-9"), returncode=0, stderr="")])
    pg = Playground(cli=cli)
    pg.run("/tmp/b", "s", "hi", session_id="pg-9")
    assert cli.calls[0]["resume"] == "pg-9"
