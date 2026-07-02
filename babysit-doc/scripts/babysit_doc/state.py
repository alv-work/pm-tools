import json
from pathlib import Path


class State:
    def __init__(self, page_id, root=None):
        self.page_id = page_id
        self._root = Path(root) if root else (Path.home() / ".config" / "babysit-doc")
        self._file = self._root / "state" / f"{page_id}.json"
        self.seen = {}
        if self._file.is_file():
            data = json.loads(self._file.read_text())
            self.seen = data.get("seen", {})

    def mark_seen(self, thread_id, updated_at):
        self.seen[thread_id] = updated_at

    def save(self, now):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps({"seen": self.seen, "last_check": now}, indent=2))
