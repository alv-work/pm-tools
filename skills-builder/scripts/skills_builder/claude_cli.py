"""Thin, injectable wrapper around the `claude` CLI in headless print mode.

`run_claude` builds the argv and runs it, returning raw stdout lines. The actual
process spawn is factored into a `runner` callable so tests inject a fake and
never touch a real subprocess. This is the ONLY module that shells out to claude.
"""
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class CliResult:
    lines: List[str]
    returncode: int
    stderr: str
    timed_out: bool = False


def build_argv(
    prompt: str,
    *,
    binary: str = "claude",
    session_id: Optional[str] = None,
    resume: Optional[str] = None,
    system_prompt: Optional[str] = None,
    append_system_prompt: Optional[str] = None,
    allowed_tools: Optional[List[str]] = None,
    disallowed_tools: Optional[List[str]] = None,
    permission_mode: Optional[str] = None,
) -> List[str]:
    argv = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if session_id:
        argv += ["--session-id", session_id]
    if resume:
        argv += ["--resume", resume]
    if system_prompt:
        argv += ["--system-prompt", system_prompt]
    if append_system_prompt:
        argv += ["--append-system-prompt", append_system_prompt]
    if allowed_tools:
        argv += ["--allowed-tools", *allowed_tools]
    if disallowed_tools:
        argv += ["--disallowed-tools", *disallowed_tools]
    if permission_mode:
        argv += ["--permission-mode", permission_mode]
    return argv


def _subprocess_runner(argv, cwd, timeout):
    proc = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
    return proc.stdout, proc.returncode, proc.stderr


def run_claude(
    prompt: str,
    *,
    cwd: Optional[str] = None,
    timeout: int = 120,
    runner: Optional[Callable] = None,
    **argv_kwargs,
) -> CliResult:
    runner = runner or _subprocess_runner
    argv = build_argv(prompt, **argv_kwargs)
    try:
        stdout, returncode, stderr = runner(argv, cwd, timeout)
    except subprocess.TimeoutExpired:
        return CliResult(lines=[], returncode=-1,
                         stderr=f"timed out after {timeout}s", timed_out=True)
    return CliResult(lines=stdout.splitlines(), returncode=returncode, stderr=stderr)
