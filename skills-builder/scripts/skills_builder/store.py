"""On-disk build state under ~/.claude/skills-builder/builds/<id>/.

Everything is human-readable and crash-durable: `meta.json` (stage, session,
skill name, timestamps), `transcript.jsonl` (append-only chat log), and the draft
skill tree at `.claude/skills/<name>/SKILL.md` — laid out so a playground session
with cwd=<build dir> discovers it as a project skill. User-level (not project) since
PMs have no meaningful cwd.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

DEFAULT_ROOT = Path.home() / ".claude" / "skills-builder" / "builds"


class StoreError(Exception):
    pass


@dataclass
class BuildMeta:
    id: str
    stage: str = "idea"
    status: str = "draft"          # draft | installed | shared
    title: str = "Untitled skill"
    skill_name: Optional[str] = None
    session_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class Store:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DEFAULT_ROOT

    def _dir(self, build_id: str) -> Path:
        return self.root / build_id

    def create(self, build_id: str, now: str, title: str = "Untitled skill") -> BuildMeta:
        d = self._dir(build_id)
        if d.exists():
            raise StoreError(f"build {build_id} already exists")
        d.mkdir(parents=True)
        meta = BuildMeta(id=build_id, title=title, created_at=now, updated_at=now)
        self.save(meta)
        return meta

    def save(self, meta: BuildMeta) -> None:
        d = self._dir(meta.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(json.dumps(asdict(meta), indent=2))

    def load(self, build_id: str) -> BuildMeta:
        p = self._dir(build_id) / "meta.json"
        if not p.exists():
            raise StoreError(f"no build {build_id}")
        d = json.loads(p.read_text())
        return BuildMeta(**{k: d[k] for k in BuildMeta.__dataclass_fields__ if k in d})

    def list(self) -> List[BuildMeta]:
        if not self.root.exists():
            return []
        metas = []
        for child in self.root.iterdir():
            if (child / "meta.json").exists():
                try:
                    metas.append(self.load(child.name))
                except StoreError:
                    continue
        return sorted(metas, key=lambda m: m.updated_at, reverse=True)

    def append_transcript(self, build_id: str, entry: dict) -> None:
        p = self._dir(build_id) / "transcript.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def read_transcript(self, build_id: str) -> List[dict]:
        p = self._dir(build_id) / "transcript.jsonl"
        if not p.exists():
            return []
        return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]

    def skills_dir(self, build_id: str) -> Path:
        return self._dir(build_id) / ".claude" / "skills"

    def draft_path(self, build_id: str, name: str) -> Path:
        return self.skills_dir(build_id) / name / "SKILL.md"

    def write_draft(self, build_id: str, name: str, content: str) -> Path:
        p = self.draft_path(build_id, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p
