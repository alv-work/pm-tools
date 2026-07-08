import subprocess
from skills_builder.claude_cli import build_argv, run_claude, CliResult


def test_build_argv_core_flags():
    argv = build_argv("hello")
    assert argv[:2] == ["claude", "-p"]
    assert "hello" in argv
    assert "--output-format" in argv and "stream-json" in argv
    assert "--verbose" in argv


def test_build_argv_resume_and_system_prompt_and_tools():
    argv = build_argv(
        "hi", resume="sess-9", system_prompt="be terse",
        disallowed_tools=["Bash", "Write"], permission_mode="plan",
    )
    assert "--resume" in argv and "sess-9" in argv
    assert "--system-prompt" in argv and "be terse" in argv
    assert "--disallowed-tools" in argv and "Bash" in argv and "Write" in argv
    assert "--permission-mode" in argv and "plan" in argv


def test_run_claude_parses_stdout_lines_via_injected_runner():
    calls = {}

    def fake_runner(argv, cwd, timeout):
        calls["argv"] = argv
        calls["cwd"] = cwd
        return "line1\nline2\n", 0, ""

    res = run_claude("hi", cwd="/tmp/build", runner=fake_runner)
    assert isinstance(res, CliResult)
    assert res.lines == ["line1", "line2"]
    assert res.returncode == 0
    assert res.timed_out is False
    assert calls["cwd"] == "/tmp/build"


def test_run_claude_timeout_sets_flag():
    def boom(argv, cwd, timeout):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    res = run_claude("hi", timeout=5, runner=boom)
    assert res.timed_out is True
    assert res.returncode != 0
