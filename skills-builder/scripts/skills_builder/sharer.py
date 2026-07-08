"""Share a finished skill with the team, or export it as a zip.

If SKILLS_BUILDER_SHARE_REPO points at a local clone of the team's marketplace
repo and git/gh are usable, `share_or_export` commits the skill to a branch and
opens a PR. Otherwise it falls back to a zip in ~/Downloads with install
instructions. The subprocess layer is injected so the PR path is testable.
"""
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

DEFAULT_DOWNLOADS = Path.home() / "Downloads"
DEFAULT_SUBDIR = "shared-skills"


class ShareError(Exception):
    pass


@dataclass
class ShareResult:
    mode: str          # "pr" | "export"
    url: str = ""
    path: str = ""


def _subprocess_runner(argv, cwd):
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return proc.stdout, proc.returncode, proc.stderr


def share_or_export(
    skill_dir,
    name: str,
    *,
    share_repo: Optional[str] = None,
    downloads: Optional[Path] = None,
    subdir: Optional[str] = None,
    runner: Optional[Callable] = None,
) -> ShareResult:
    skill_dir = Path(skill_dir)
    if not (skill_dir / "SKILL.md").exists():
        raise ShareError("There's no skill to share yet.")
    runner = runner or _subprocess_runner
    share_repo = share_repo if share_repo is not None else os.environ.get("SKILLS_BUILDER_SHARE_REPO")

    if share_repo and _tools_available(runner):
        return _open_pr(skill_dir, name, Path(share_repo),
                        subdir or os.environ.get("SKILLS_BUILDER_SHARE_SUBDIR", DEFAULT_SUBDIR),
                        runner)
    return _export_zip(skill_dir, name, Path(downloads) if downloads else DEFAULT_DOWNLOADS)


def _tools_available(runner) -> bool:
    for tool in (["git", "--version"], ["gh", "--version"]):
        try:
            _, rc, _ = runner(tool, None)
        except (OSError, FileNotFoundError):
            return False
        if rc != 0:
            return False
    return True


def _run(runner, argv, cwd, what):
    out, rc, err = runner(argv, cwd)
    if rc != 0:
        raise ShareError(f"{what} failed: {(err or out or '').strip()[:400]}")
    return out


def _open_pr(skill_dir, name, repo, subdir, runner) -> ShareResult:
    if not repo.exists():
        raise ShareError(f"Share repo not found at {repo}.")
    dest = repo / subdir / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_dir, dest)

    branch = f"skill/{name}"
    _run(runner, ["git", "checkout", "-b", branch], str(repo), "create branch")
    _run(runner, ["git", "add", "-A"], str(repo), "stage")
    _run(runner, ["git", "commit", "-m", f"Add skill: {name}"], str(repo), "commit")
    _run(runner, ["git", "push", "-u", "origin", branch], str(repo), "push")
    out = _run(runner, ["gh", "pr", "create", "--fill"], str(repo), "open PR")
    url = out.strip().splitlines()[-1] if out.strip() else ""
    return ShareResult(mode="pr", url=url)


def _export_zip(skill_dir, name, downloads) -> ShareResult:
    downloads.mkdir(parents=True, exist_ok=True)
    zip_path = downloads / f"{name}-skill.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in skill_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(Path(name) / f.relative_to(skill_dir)))
        zf.writestr(
            f"{name}/INSTALL.txt",
            "To install this skill:\n"
            f"1. Unzip this file.\n"
            f"2. Copy the '{name}' folder into ~/.claude/skills/\n"
            "3. Start a new Claude session — it activates on its own.\n",
        )
    return ShareResult(mode="export", path=str(zip_path))
