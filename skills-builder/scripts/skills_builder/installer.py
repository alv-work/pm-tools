"""Install a finished draft into ~/.claude/skills/ and manage installed skills.

Copies the build's `.claude/skills/<name>/` tree to the user's global skills dir,
drops a `.skills-builder.json` provenance marker, and keeps the SKILL.md `name:`
in lockstep with the install directory (so installing under a new name stays
consistent). Name collisions raise unless `overwrite=True`.
"""
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_SKILLS_ROOT = Path.home() / ".claude" / "skills"

_NAME_LINE = re.compile(r"^name:.*$", re.MULTILINE)


class InstallError(Exception):
    pass


@dataclass
class InstallResult:
    name: str
    path: str
    overwritten: bool


class Installer:
    def __init__(self, skills_root: Optional[Path] = None):
        self.skills_root = Path(skills_root) if skills_root else DEFAULT_SKILLS_ROOT

    def is_installed(self, name: str) -> bool:
        return (self.skills_root / name / "SKILL.md").exists()

    def install(self, src_skill_dir, name: str, provenance: dict, overwrite: bool = False) -> InstallResult:
        src = Path(src_skill_dir)
        if not (src / "SKILL.md").exists():
            raise InstallError("There's no skill draft to install yet.")
        dest = self.skills_root / name
        existed = dest.exists()
        if existed and not overwrite:
            raise InstallError(f"A skill named '{name}' is already installed.")
        if existed:
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        self._sync_name(dest / "SKILL.md", name)
        (dest / ".skills-builder.json").write_text(json.dumps(provenance, indent=2))
        return InstallResult(name=name, path=str(dest), overwritten=existed)

    def uninstall(self, name: str) -> None:
        dest = self.skills_root / name
        if dest.exists():
            shutil.rmtree(dest)

    @staticmethod
    def _sync_name(skill_md: Path, name: str) -> None:
        text = skill_md.read_text()
        if _NAME_LINE.search(text):
            text = _NAME_LINE.sub(f"name: {name}", text, count=1)
            skill_md.write_text(text)
