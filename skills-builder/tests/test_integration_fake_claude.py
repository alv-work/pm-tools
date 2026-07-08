"""End-to-end through a real subprocess, using the fake claude executable.

Proves claude_cli -> stream -> protocol -> engine work against actual process
output, not just injected fakes. Deterministic, no API cost.
"""
import os
from pathlib import Path

import pytest

from skills_builder.claude_cli import run_claude
from skills_builder.engine import Engine, EngineError

FAKE = str(Path(__file__).parent / "fixtures" / "fake_claude.py")


def _cli_using_fake(mode="valid"):
    env_binary = FAKE

    def cli(prompt, **kwargs):
        old = os.environ.get("SKILLS_BUILDER_FAKE_MODE")
        os.environ["SKILLS_BUILDER_FAKE_MODE"] = mode
        try:
            return run_claude(prompt, binary=env_binary, **kwargs)
        finally:
            if old is None:
                os.environ.pop("SKILLS_BUILDER_FAKE_MODE", None)
            else:
                os.environ["SKILLS_BUILDER_FAKE_MODE"] = old

    return cli


def test_run_claude_real_subprocess_returns_stream_lines():
    os.environ["SKILLS_BUILDER_FAKE_MODE"] = "valid"
    try:
        res = run_claude("hi", binary=FAKE)
    finally:
        os.environ.pop("SKILLS_BUILDER_FAKE_MODE", None)
    assert res.returncode == 0
    assert any('"type": "result"' in line for line in res.lines)


def test_engine_end_to_end_with_fake_executable():
    eng = Engine(cli=_cli_using_fake("valid"))
    res = eng.turn("start building a skill")
    assert res.turn.stage == "shape"
    assert res.turn.widget.type == "free_text"
    assert res.session_id == "fake-sess"


def test_engine_surfaces_cli_crash_as_engine_error():
    eng = Engine(cli=_cli_using_fake("crash"))
    with pytest.raises(EngineError) as ei:
        eng.turn("hi")
    assert ei.value.kind == "crash"
    assert "not logged in" in (ei.value.detail or "")
