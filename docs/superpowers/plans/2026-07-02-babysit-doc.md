# babysit-doc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `babysit-doc` v1 — a `pm-tools` plugin that watches a Confluence page's comment threads and surfaces Claude-drafted replies for the human to approve before anything posts.

**Architecture:** A zero-dependency Python package does the I/O (`scan` fetches new/updated threads + page text as JSON; `post` sends one approved reply). Claude, driven by the command file, does the drafting and mediates approval. A `DocSource` interface isolates Confluence so Word/Graph drops in later. Per-page JSON state dedups threads across passes.

**Tech Stack:** Python 3.10+ (standard library only — `urllib`, `json`, `base64`, `re`, `pathlib`), pytest for tests. Confluence Cloud REST API v2.

## Global Constraints

- Python 3.10+, **standard library only** — no `requests`, no `anthropic`, no third-party runtime deps. Tests may use `pytest`.
- **Draft-only:** the `scan` path never posts; `post` runs only per an item the human approved. No auto-post anywhere in v1.
- Platform: **Confluence Cloud only** in v1. All Confluence specifics live behind the `DocSource` interface.
- Auth via env first, then `~/.config/babysit-doc/config.json`: `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`. Basic auth = `base64(email:token)`.
- Confluence v2 base path prefix: `<base_url>/api/v2/...` where `base_url` ends in `/wiki`.
- Repo root is `/Users/avaibhav/Documents/skills` (the `pm-tools` repo). Plugin dir: `babysit-doc/`. Package importable via `PYTHONPATH=babysit-doc/scripts`.
- Commit after every task with author `Alabhya Vaibhav <alabhya.vaibhav1997@gmail.com>` (repo default is a work identity, so pass `-c user.email=...` or set it once in Task 1).

---

### Task 1: Plugin scaffold + config loader

**Files:**
- Create: `babysit-doc/.claude-plugin/plugin.json`
- Create: `babysit-doc/scripts/babysit_doc/__init__.py` (empty)
- Create: `babysit-doc/scripts/babysit_doc/config.py`
- Create: `babysit-doc/tests/test_config.py`
- Create: `babysit-doc/pyproject.toml` (pytest config only)

**Interfaces:**
- Produces: `load_config(env: dict | None = None) -> Config` where `Config` is a dataclass with `.base_url: str`, `.email: str`, `.token: str`. Raises `ConfigError(str)` listing every missing key. `ConfigError(Exception)`.

- [ ] **Step 1: Set the repo commit identity once**

```bash
cd /Users/avaibhav/Documents/skills
git config user.name "Alabhya Vaibhav"
git config user.email "alabhya.vaibhav1997@gmail.com"
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["babysit-doc/tests"]
pythonpath = ["babysit-doc/scripts"]
```

- [ ] **Step 3: Create `plugin.json`**

`babysit-doc/.claude-plugin/plugin.json`:
```json
{
  "name": "babysit-doc",
  "description": "Watch a Confluence page's comment threads and surface Claude-drafted replies to approve before posting.",
  "version": "0.1.0",
  "author": { "name": "Alabhya Vaibhav" }
}
```

- [ ] **Step 4: Write the failing test**

`babysit-doc/tests/test_config.py`:
```python
import pytest
from babysit_doc.config import load_config, Config, ConfigError


def test_loads_from_env():
    env = {
        "CONFLUENCE_BASE_URL": "https://acme.atlassian.net/wiki",
        "CONFLUENCE_EMAIL": "me@acme.com",
        "CONFLUENCE_API_TOKEN": "tok",
    }
    cfg = load_config(env)
    assert cfg == Config("https://acme.atlassian.net/wiki", "me@acme.com", "tok")


def test_strips_trailing_slash_on_base_url():
    env = {
        "CONFLUENCE_BASE_URL": "https://acme.atlassian.net/wiki/",
        "CONFLUENCE_EMAIL": "me@acme.com",
        "CONFLUENCE_API_TOKEN": "tok",
    }
    assert load_config(env).base_url == "https://acme.atlassian.net/wiki"


def test_missing_keys_lists_all_of_them():
    with pytest.raises(ConfigError) as e:
        load_config({})
    msg = str(e.value)
    assert "CONFLUENCE_BASE_URL" in msg
    assert "CONFLUENCE_EMAIL" in msg
    assert "CONFLUENCE_API_TOKEN" in msg
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd /Users/avaibhav/Documents/skills && python -m pytest babysit-doc/tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.config'`

- [ ] **Step 6: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/config.py`:
```python
import json
from dataclasses import dataclass
from pathlib import Path

KEYS = ("CONFLUENCE_BASE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN")
CONFIG_FILE = Path.home() / ".config" / "babysit-doc" / "config.json"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    base_url: str
    email: str
    token: str


def _from_file():
    if CONFIG_FILE.is_file():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError as e:
            raise ConfigError(f"invalid JSON in {CONFIG_FILE}: {e}")
    return {}


def load_config(env=None):
    import os
    env = os.environ if env is None else env
    file_vals = _from_file()
    vals = {k: env.get(k) or file_vals.get(k) for k in KEYS}
    missing = [k for k in KEYS if not vals[k]]
    if missing:
        raise ConfigError(
            "missing Confluence credentials: " + ", ".join(missing)
            + f"\nset them as env vars or in {CONFIG_FILE}"
        )
    return Config(vals["CONFLUENCE_BASE_URL"].rstrip("/"),
                  vals["CONFLUENCE_EMAIL"], vals["CONFLUENCE_API_TOKEN"])
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_config.py -q`
Expected: PASS (3 passed)

- [ ] **Step 8: Commit**

```bash
git add babysit-doc/ pyproject.toml
git commit -m "feat(babysit-doc): plugin scaffold + config loader"
```

---

### Task 2: Confluence HTTP client

**Files:**
- Create: `babysit-doc/scripts/babysit_doc/confluence_client.py`
- Create: `babysit-doc/tests/test_confluence_client.py`

**Interfaces:**
- Consumes: `Config` from Task 1.
- Produces: `ConfluenceClient(cfg: Config, opener=urllib.request.urlopen)`. Methods:
  - `.get(path: str, params: dict | None = None) -> dict` — GET `<base_url><path>`, returns parsed JSON.
  - `.post(path: str, body: dict) -> dict` — POST JSON, returns parsed JSON.
  - Raises `AuthError` on 401/403, `ApiError(status, msg)` on other 4xx/5xx. Both subclass `ClientError(Exception)`. The `opener` seam takes `(urllib.request.Request)` and returns a file-like with `.read()` and `.status`; tests inject a fake.

- [ ] **Step 1: Write the failing test**

`babysit-doc/tests/test_confluence_client.py`:
```python
import io, json
import pytest
from babysit_doc.config import Config
from babysit_doc.confluence_client import ConfluenceClient, AuthError, ApiError
import urllib.error


def make_client(recorder, response=None, error=None):
    def opener(req, timeout=None):
        recorder["req"] = req
        if error:
            raise error
        body = json.dumps(response or {}).encode()
        r = io.BytesIO(body); r.status = 200
        return r
    cfg = Config("https://acme.atlassian.net/wiki", "me@acme.com", "tok")
    return ConfluenceClient(cfg, opener=opener), recorder


def test_get_builds_url_auth_and_parses_json():
    rec = {}
    client, rec = make_client(rec, response={"results": [1, 2]})
    out = client.get("/api/v2/pages/5/footer-comments", {"limit": 100})
    assert out == {"results": [1, 2]}
    req = rec["req"]
    assert req.full_url == "https://acme.atlassian.net/wiki/api/v2/pages/5/footer-comments?limit=100"
    assert req.get_header("Authorization").startswith("Basic ")


def test_401_raises_auth_error():
    rec = {}
    err = urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b"nope"))
    client, _ = make_client(rec, error=err)
    with pytest.raises(AuthError):
        client.get("/api/v2/pages/5/footer-comments")


def test_500_raises_api_error_with_status():
    rec = {}
    err = urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO(b"boom"))
    client, _ = make_client(rec, error=err)
    with pytest.raises(ApiError) as e:
        client.get("/x")
    assert e.value.status == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_confluence_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.confluence_client'`

- [ ] **Step 3: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/confluence_client.py`:
```python
import base64, json, urllib.parse, urllib.request, urllib.error


class ClientError(Exception):
    pass


class AuthError(ClientError):
    pass


class ApiError(ClientError):
    def __init__(self, status, msg):
        super().__init__(f"HTTP {status}: {msg}")
        self.status = status


class ConfluenceClient:
    def __init__(self, cfg, opener=urllib.request.urlopen):
        self._base = cfg.base_url
        self._opener = opener
        token = base64.b64encode(f"{cfg.email}:{cfg.token}".encode()).decode()
        self._auth = f"Basic {token}"

    def _send(self, method, path, params=None, body=None):
        url = self._base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self._auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            resp = self._opener(req, timeout=30)
            raw = resp.read()
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError("Confluence rejected the credentials (check email/token/permissions)")
            raise ApiError(e.code, e.reason)

    def get(self, path, params=None):
        return self._send("GET", path, params=params)

    def post(self, path, body):
        return self._send("POST", path, body=body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_confluence_client.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): confluence HTTP client with auth + error mapping"
```

---

### Task 3: DocSource interface + Thread model

**Files:**
- Create: `babysit-doc/scripts/babysit_doc/sources/__init__.py` (empty)
- Create: `babysit-doc/scripts/babysit_doc/sources/base.py`
- Create: `babysit-doc/tests/test_base.py`

**Interfaces:**
- Produces:
  - `Thread` dataclass: `id: str`, `type: str` (`"footer"|"inline"`), `author: str`, `created_at: str`, `updated_at: str`, `comment_text: str`, `permalink: str`, `anchor: str | None`. Method `.to_dict() -> dict` returning all fields.
  - `Page` dataclass: `id: str`, `title: str`, `url: str`, `text: str`. `.to_dict()`.
  - `DocSource` ABC with abstract methods: `resolve(ref: str) -> Page`, `list_threads(page: Page) -> list[Thread]`, `post_reply(thread: Thread, text: str) -> None`.

- [ ] **Step 1: Write the failing test**

`babysit-doc/tests/test_base.py`:
```python
import pytest
from babysit_doc.sources.base import Thread, Page, DocSource


def test_thread_to_dict_roundtrips_fields():
    t = Thread("11", "inline", "Sam", "2026-07-01T10:00:00Z",
               "2026-07-01T11:00:00Z", "why here?", "https://x/11", "the API line")
    d = t.to_dict()
    assert d["id"] == "11" and d["type"] == "inline" and d["anchor"] == "the API line"
    assert d["comment_text"] == "why here?"


def test_docsource_is_abstract():
    with pytest.raises(TypeError):
        DocSource()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_base.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.sources'`

- [ ] **Step 3: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/sources/base.py`:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class Page:
    id: str
    title: str
    url: str
    text: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Thread:
    id: str
    type: str
    author: str
    created_at: str
    updated_at: str
    comment_text: str
    permalink: str
    anchor: str | None

    def to_dict(self):
        return asdict(self)


class DocSource(ABC):
    @abstractmethod
    def resolve(self, ref: str) -> Page: ...

    @abstractmethod
    def list_threads(self, page: Page) -> list: ...

    @abstractmethod
    def post_reply(self, thread: Thread, text: str) -> None: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_base.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): DocSource interface + Thread/Page models"
```

---

### Task 4: ConfluenceSource — resolve + list_threads

**Files:**
- Create: `babysit-doc/scripts/babysit_doc/sources/confluence.py`
- Create: `babysit-doc/tests/test_confluence_source.py`

**Interfaces:**
- Consumes: `ConfluenceClient` (Task 2), `Page`/`Thread`/`DocSource` (Task 3).
- Produces: `ConfluenceSource(client: ConfluenceClient)`.
  - `resolve(ref)`: accepts a full page URL (`.../pages/<id>/...`) or a bare numeric id. Returns `Page` with plain-text `text` (storage body stripped of tags). Raises `ValueError` if no id found.
  - `list_threads(page)`: fetches open footer + inline comments, builds one `Thread` per top-level comment (reply chain concatenated into `comment_text`, `updated_at` = latest reply timestamp). `anchor` = inline original selection text or `None`.
  - Helpers (module-level, tested): `extract_page_id(ref) -> str`, `strip_tags(html) -> str`.

- [ ] **Step 1: Write the failing test**

`babysit-doc/tests/test_confluence_source.py`:
```python
import pytest
from babysit_doc.sources.confluence import ConfluenceSource, extract_page_id, strip_tags


def test_extract_page_id_from_url():
    url = "https://acme.atlassian.net/wiki/spaces/ENG/pages/12345/My+Spec"
    assert extract_page_id(url) == "12345"


def test_extract_page_id_from_bare_id():
    assert extract_page_id("12345") == "12345"


def test_extract_page_id_rejects_garbage():
    with pytest.raises(ValueError):
        extract_page_id("https://acme.atlassian.net/wiki/spaces/ENG")


def test_strip_tags_produces_plain_text():
    assert strip_tags("<p>Hello <b>world</b></p>") == "Hello world"


class FakeClient:
    def __init__(self, responses):
        self.responses = responses  # dict: path -> dict
    def get(self, path, params=None):
        return self.responses[path]
    def post(self, path, body):
        raise AssertionError("list should not POST")


def test_list_threads_builds_threads_with_reply_chain():
    page_id = "5"
    responses = {
        f"/api/v2/pages/{page_id}/footer-comments": {"results": [
            {"id": "100", "version": {"createdAt": "2026-07-01T10:00:00Z", "authorId": "u1"},
             "body": {"storage": {"value": "<p>Can we cut scope?</p>"}},
             "_links": {"webui": "/x/100"}}
        ], "_links": {}},
        f"/api/v2/pages/{page_id}/inline-comments": {"results": [], "_links": {}},
        "/api/v2/footer-comments/100/children": {"results": [
            {"id": "101", "version": {"createdAt": "2026-07-01T12:00:00Z", "authorId": "u2"},
             "body": {"storage": {"value": "<p>Agreed</p>"}}, "_links": {"webui": "/x/101"}}
        ], "_links": {}},
    }
    src = ConfluenceSource(FakeClient(responses))
    page = type("P", (), {"id": page_id, "url": "https://acme.atlassian.net/wiki/x"})()
    threads = src.list_threads(page)
    assert len(threads) == 1
    t = threads[0]
    assert t.id == "100" and t.type == "footer"
    assert "Can we cut scope?" in t.comment_text and "Agreed" in t.comment_text
    assert t.updated_at == "2026-07-01T12:00:00Z"   # latest reply wins
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_confluence_source.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.sources.confluence'`

- [ ] **Step 3: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/sources/confluence.py`:
```python
import re, html
from .base import DocSource, Page, Thread

_ID_RE = re.compile(r"/pages/(\d+)")


def extract_page_id(ref):
    ref = ref.strip()
    if ref.isdigit():
        return ref
    m = _ID_RE.search(ref)
    if not m:
        raise ValueError(f"could not find a page id in: {ref}")
    return m.group(1)


def strip_tags(value):
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(text).strip()


class ConfluenceSource(DocSource):
    def __init__(self, client):
        self._c = client

    def resolve(self, ref):
        pid = extract_page_id(ref)
        data = self._c.get(f"/api/v2/pages/{pid}", {"body-format": "storage"})
        body = (data.get("body", {}).get("storage", {}) or {}).get("value", "")
        base = re.sub(r"/wiki.*$", "/wiki", ref) if "/wiki" in ref else ""
        webui = (data.get("_links", {}) or {}).get("webui", "")
        url = (base + webui) if webui else ref
        return Page(id=pid, title=data.get("title", ""), url=url, text=strip_tags(body))

    def _paged(self, path):
        # v1: single page of up to 100; pagination deferred (noted in plan).
        data = self._c.get(path, {"body-format": "storage", "limit": 100})
        return data.get("results", [])

    def _thread_from(self, kind, top):
        tid = str(top["id"])
        children = self._paged(f"/api/v2/{kind}-comments/{tid}/children")
        chain = [top] + children
        parts, updated = [], top["version"]["createdAt"]
        for c in chain:
            parts.append(strip_tags(c["body"]["storage"]["value"]))
            updated = max(updated, c["version"]["createdAt"])
        anchor = None
        if kind == "inline":
            props = top.get("properties", {}) or {}
            anchor = props.get("inline-original-selection") or props.get("inlineOriginalSelection")
        return Thread(
            id=tid, type=kind, author=str(top["version"].get("authorId", "")),
            created_at=top["version"]["createdAt"], updated_at=updated,
            comment_text="\n\n".join(p for p in parts if p),
            permalink=(top.get("_links", {}) or {}).get("webui", ""), anchor=anchor,
        )

    def list_threads(self, page):
        threads = []
        for kind in ("footer", "inline"):
            for top in self._paged(f"/api/v2/pages/{page.id}/{kind}-comments"):
                threads.append(self._thread_from(kind, top))
        return threads

    def post_reply(self, thread, text):
        raise NotImplementedError  # Task 5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_confluence_source.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): confluence resolve + list_threads"
```

> **v1 simplification (noted, not a gap):** `_paged` fetches a single page of up to 100 comments; cursor pagination is deferred. A page with >100 top-level comments will only surface the first 100 — acceptable for v1, revisit if hit.

---

### Task 5: ConfluenceSource.post_reply

**Files:**
- Modify: `babysit-doc/scripts/babysit_doc/sources/confluence.py` (replace the `post_reply` stub)
- Modify: `babysit-doc/tests/test_confluence_source.py` (add a test)

**Interfaces:**
- Produces: `ConfluenceSource.post_reply(thread, text)` POSTs to `/api/v2/{thread.type}-comments` with `{"pageId": ..., "parentCommentId": thread.id, "body": {"representation": "storage", "value": text}}`. Needs the page id; `post_reply` reads it from `thread`, so **`Thread` gains no field** — instead the CLI passes page id. To keep `post_reply` self-contained, it takes page id via the reply body built from `thread`. Signature stays `post_reply(thread, text)`; page id is carried on the source as `self._page_id` set during `list_threads`/`resolve`. Simpler: change signature to `post_reply(thread, text, page_id)`.

  **Decision:** signature is `post_reply(self, thread, text, page_id: str) -> None`. Update `DocSource.post_reply` abstract signature to match.

- [ ] **Step 1: Update the abstract signature**

In `sources/base.py`, change:
```python
    @abstractmethod
    def post_reply(self, thread: Thread, text: str) -> None: ...
```
to:
```python
    @abstractmethod
    def post_reply(self, thread: Thread, text: str, page_id: str) -> None: ...
```

- [ ] **Step 2: Write the failing test**

Add to `babysit-doc/tests/test_confluence_source.py`:
```python
def test_post_reply_posts_to_correct_endpoint():
    calls = {}
    class PostClient:
        def get(self, path, params=None): raise AssertionError
        def post(self, path, body):
            calls["path"] = path; calls["body"] = body
            return {"id": "999"}
    from babysit_doc.sources.base import Thread
    t = Thread("100", "footer", "u1", "t", "t", "c", "/x/100", None)
    ConfluenceSource(PostClient()).post_reply(t, "Sounds good", "5")
    assert calls["path"] == "/api/v2/footer-comments"
    assert calls["body"]["pageId"] == "5"
    assert calls["body"]["parentCommentId"] == "100"
    assert calls["body"]["body"] == {"representation": "storage", "value": "Sounds good"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_confluence_source.py::test_post_reply_posts_to_correct_endpoint -q`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 4: Replace the `post_reply` stub**

```python
    def post_reply(self, thread, text, page_id):
        self._c.post(f"/api/v2/{thread.type}-comments", {
            "pageId": page_id,
            "parentCommentId": thread.id,
            "body": {"representation": "storage", "value": text},
        })
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_confluence_source.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): post_reply to footer/inline threads"
```

---

### Task 6: State store

**Files:**
- Create: `babysit-doc/scripts/babysit_doc/state.py`
- Create: `babysit-doc/tests/test_state.py`

**Interfaces:**
- Produces: `State(page_id: str, root: Path | None = None)`:
  - `.seen: dict[str, str]` (thread id → last-seen `updated_at`), loaded from disk on init.
  - `.mark_seen(thread_id: str, updated_at: str) -> None`
  - `.save() -> None` (writes `<root>/state/<page_id>.json` with `seen` + `last_check`)
  - Default `root` = `~/.config/babysit-doc`. `last_check` set to a value passed to `save(now)`.

- [ ] **Step 1: Write the failing test**

`babysit-doc/tests/test_state.py`:
```python
from babysit_doc.state import State


def test_roundtrips_seen_via_disk(tmp_path):
    s = State("5", root=tmp_path)
    assert s.seen == {}
    s.mark_seen("100", "2026-07-01T12:00:00Z")
    s.save(now="2026-07-01T13:00:00Z")

    s2 = State("5", root=tmp_path)
    assert s2.seen == {"100": "2026-07-01T12:00:00Z"}


def test_separate_pages_have_separate_state(tmp_path):
    State("5", root=tmp_path).save(now="t")
    a = State("5", root=tmp_path); a.mark_seen("1", "t"); a.save(now="t")
    b = State("6", root=tmp_path)
    assert b.seen == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_state.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.state'`

- [ ] **Step 3: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/state.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_state.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): per-page state store"
```

---

### Task 7: Diff — queue new/updated threads

**Files:**
- Create: `babysit-doc/scripts/babysit_doc/diff.py`
- Create: `babysit-doc/tests/test_diff.py`

**Interfaces:**
- Consumes: `Thread` (Task 3), `State.seen` (Task 6).
- Produces: `queue_new_or_updated(threads: list[Thread], seen: dict[str, str]) -> list[Thread]` — returns threads whose id is not in `seen`, or whose `updated_at` is newer than `seen[id]` (string compare is valid for ISO-8601 UTC timestamps).

- [ ] **Step 1: Write the failing test**

`babysit-doc/tests/test_diff.py`:
```python
from babysit_doc.diff import queue_new_or_updated
from babysit_doc.sources.base import Thread


def mk(id, updated):
    return Thread(id, "footer", "u", "c", updated, "text", "/x", None)


def test_new_thread_is_queued():
    assert [t.id for t in queue_new_or_updated([mk("1", "t2")], {})] == ["1"]


def test_unchanged_thread_is_skipped():
    assert queue_new_or_updated([mk("1", "t2")], {"1": "t2"}) == []


def test_updated_thread_is_requeued():
    out = queue_new_or_updated([mk("1", "2026-07-02T00:00:00Z")], {"1": "2026-07-01T00:00:00Z"})
    assert [t.id for t in out] == ["1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_diff.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.diff'`

- [ ] **Step 3: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/diff.py`:
```python
def queue_new_or_updated(threads, seen):
    out = []
    for t in threads:
        last = seen.get(t.id)
        if last is None or t.updated_at > last:
            out.append(t)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest babysit-doc/tests/test_diff.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): new/updated thread diff"
```

---

### Task 8: CLI entrypoint — `scan` and `post`

**Files:**
- Create: `babysit-doc/scripts/babysit_doc/__main__.py`
- Create: `babysit-doc/tests/test_main.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `python -m babysit_doc scan <ref>` and `python -m babysit_doc post <ref> <thread_id> <type> <text>`.
  - `scan`: resolves page, lists threads, diffs vs state, prints JSON `{"page": {...}, "threads": [ {thread fields...} ]}` (only queued threads). Does NOT mark seen (nothing handled yet) — but records `last_check`.
  - `post`: posts one reply, then marks that thread seen with its current server `updated_at` (re-fetched) and saves.
  - `main(argv, source_factory=None, state_factory=None) -> int` — factories injectable for tests; default builds real `ConfluenceSource`/`State`. Prints JSON to stdout; errors to stderr, returns non-zero.

- [ ] **Step 1: Write the failing test**

`babysit-doc/tests/test_main.py`:
```python
import json
from babysit_doc.__main__ import main
from babysit_doc.sources.base import Page, Thread


class FakeSource:
    def __init__(self):
        self.posted = []
    def resolve(self, ref):
        return Page("5", "Spec", "https://x/5", "the whole doc text")
    def list_threads(self, page):
        return [Thread("100", "footer", "u1", "t", "2026-07-02T00:00:00Z", "Cut scope?", "/x/100", None)]
    def post_reply(self, thread, text, page_id):
        self.posted.append((thread.id, text, page_id))


def test_scan_emits_page_and_queued_threads(capsys, tmp_path):
    from babysit_doc.state import State
    rc = main(["scan", "5"],
              source_factory=lambda cfg: FakeSource(),
              state_factory=lambda pid: State(pid, root=tmp_path))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["page"]["text"] == "the whole doc text"
    assert [t["id"] for t in out["threads"]] == ["100"]


def test_scan_skips_already_seen(capsys, tmp_path):
    from babysit_doc.state import State
    s = State("5", root=tmp_path); s.mark_seen("100", "2026-07-02T00:00:00Z"); s.save(now="t")
    rc = main(["scan", "5"],
              source_factory=lambda cfg: FakeSource(),
              state_factory=lambda pid: State(pid, root=tmp_path))
    out = json.loads(capsys.readouterr().out)
    assert out["threads"] == []


def test_post_calls_source_and_marks_seen(capsys, tmp_path):
    from babysit_doc.state import State
    fake = FakeSource()
    rc = main(["post", "5", "100", "footer", "Sounds good"],
              source_factory=lambda cfg: fake,
              state_factory=lambda pid: State(pid, root=tmp_path))
    assert rc == 0
    assert fake.posted == [("100", "Sounds good", "5")]
    assert State("5", root=tmp_path).seen.get("100") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest babysit-doc/tests/test_main.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'babysit_doc.__main__'`

- [ ] **Step 3: Write minimal implementation**

`babysit-doc/scripts/babysit_doc/__main__.py`:
```python
import json, sys
from datetime import datetime, timezone
from .config import load_config, ConfigError
from .confluence_client import ConfluenceClient, ClientError
from .sources.confluence import ConfluenceSource
from .state import State
from .diff import queue_new_or_updated


def _default_source(cfg):
    return ConfluenceSource(ConfluenceClient(cfg))


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None, source_factory=None, state_factory=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: babysit_doc scan <ref> | post <ref> <thread_id> <type> <text>", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]

    try:
        cfg = load_config()
        source = (source_factory or _default_source)(cfg)
    except (ConfigError, ClientError) as e:
        print(f"babysit-doc: {e}", file=sys.stderr)
        return 1

    make_state = state_factory or (lambda pid: State(pid))

    try:
        if cmd == "scan":
            page = source.resolve(rest[0])
            state = make_state(page.id)
            queued = queue_new_or_updated(source.list_threads(page), state.seen)
            state.save(now=_now())
            print(json.dumps({
                "page": page.to_dict(),
                "threads": [t.to_dict() for t in queued],
            }, indent=2))
            return 0

        if cmd == "post":
            ref, thread_id, ttype, text = rest[0], rest[1], rest[2], rest[3]
            page = source.resolve(ref)
            state = make_state(page.id)
            thread = next((t for t in source.list_threads(page) if t.id == thread_id), None)
            if thread is None:
                print(f"babysit-doc: thread {thread_id} not found", file=sys.stderr)
                return 1
            source.post_reply(thread, text, page.id)
            state.mark_seen(thread_id, thread.updated_at)
            state.save(now=_now())
            print(json.dumps({"posted": thread_id}))
            return 0

        print(f"babysit-doc: unknown command {cmd!r}", file=sys.stderr)
        return 2
    except ClientError as e:
        print(f"babysit-doc: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest babysit-doc -q`
Expected: PASS (all tests across files)

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/
git commit -m "feat(babysit-doc): scan/post CLI entrypoint"
```

---

### Task 9: Command file, drafting instructions, marketplace entry, README

**Files:**
- Create: `babysit-doc/commands/babysit-doc.md`
- Modify: `.claude-plugin/marketplace.json` (add the plugin)
- Modify: `README.md` (add babysit-doc to the plugin list)

**Interfaces:**
- Consumes: `python -m babysit_doc scan/post` (Task 8).
- Produces: the `/babysit-doc` slash command; the drafting/approval behavior is specified here as instructions to Claude.

- [ ] **Step 1: Write the command file**

`babysit-doc/commands/babysit-doc.md`:
````markdown
---
description: Watch a Confluence page's comment threads; draft replies for you to approve before posting
argument-hint: "<confluence-page-url-or-id>"
allowed-tools: Bash(python3:*)
---

You are babysitting a Confluence doc's comments. Do exactly this:

1. Scan for new/updated threads:

```
python3 -m babysit_doc scan "$ARGUMENTS"
```

Run it from the plugin's script dir so the package imports:
```
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" python3 -m babysit_doc scan "$ARGUMENTS"
```

2. Parse the JSON. `page.text` is the full doc; `threads[]` are the comments needing attention.

3. If `threads` is empty, tell the user "No new comments" and stop.

4. For EACH thread, using `page.text` as context and the thread's `comment_text` (and `anchor` if present):
   - Decide if it warrants a reply (a question, request, or point addressed to the author). Skip pure FYIs.
   - Draft a concise, professional reply in the author's voice.
   - Judge your confidence: HIGH if the doc clearly supports the answer, LOW if you're guessing or it needs a human decision.

5. Present every draft to the user together, one block each:
   `[thread id] · confidence · author` / the comment / your draft. Flag LOW ones clearly.

6. Ask the user to approve, edit, or skip each. Do NOT post anything yet.

7. For each APPROVED (or edited) draft, post it:

```
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" python3 -m babysit_doc post "$ARGUMENTS" "<thread_id>" "<type>" "<final_text>"
```

Use the thread's `id` and `type` from the scan JSON. Report which threads posted.

Never post a reply the user did not approve. Never auto-post.
````

- [ ] **Step 2: Add the plugin to the marketplace**

In `.claude-plugin/marketplace.json`, add to the `plugins` array:
```json
{
  "name": "babysit-doc",
  "source": "./babysit-doc",
  "description": "Watch a Confluence page's comment threads and surface Claude-drafted replies to approve before posting.",
  "version": "0.1.0"
}
```

- [ ] **Step 3: Add babysit-doc to the README plugin list**

Under `## Plugins` in `README.md`, add:
```markdown
### babysit-doc
Watches a Confluence page's comment threads and drafts replies for you to approve before anything posts. Pair with `/loop` for continuous watching: `/loop 10m /babysit-doc <page-url>`. Needs `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`.
```

- [ ] **Step 4: Validate the manifests**

Run:
```bash
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); json.load(open('babysit-doc/.claude-plugin/plugin.json')); print('manifests valid')"
```
Expected: `manifests valid`

- [ ] **Step 5: Commit**

```bash
git add babysit-doc/ .claude-plugin/marketplace.json README.md
git commit -m "feat(babysit-doc): slash command, drafting instructions, marketplace entry"
```

---

### Task 10: End-to-end smoke test against a real page (gated, manual)

**Files:** none (manual verification)

**Interfaces:** exercises the full stack with real credentials.

- [ ] **Step 1: Export test credentials**

```bash
export CONFLUENCE_BASE_URL="https://<site>.atlassian.net/wiki"
export CONFLUENCE_EMAIL="<you>@<domain>"
export CONFLUENCE_API_TOKEN="<token from id.atlassian.com/manage-profile/security/api-tokens>"
```

- [ ] **Step 2: Scan a real page with at least one comment**

```bash
PYTHONPATH="babysit-doc/scripts" python3 -m babysit_doc scan "<page-url>"
```
Expected: JSON with `page.title`, non-empty `page.text`, and any open threads. Confirm a comment you can see appears in `threads`.

- [ ] **Step 3: Post a reply to a scratch thread and verify in the UI**

```bash
PYTHONPATH="babysit-doc/scripts" python3 -m babysit_doc post "<page-url>" "<thread_id>" "footer" "test reply from babysit-doc"
```
Expected: `{"posted": "<thread_id>"}`, and the reply is visible under that comment in Confluence.

- [ ] **Step 4: Re-scan and confirm the handled thread is gone**

```bash
PYTHONPATH="babysit-doc/scripts" python3 -m babysit_doc scan "<page-url>"
```
Expected: the posted-to thread no longer appears (marked seen), unless someone replied again.

- [ ] **Step 5: Note results**

Record any API-shape surprises (field names, inline anchor availability) in the spec's deferred list. No commit unless code changed.

---

## Self-Review

**Spec coverage:**
- `DocSource` interface → Task 3. ConfluenceSource resolve/list/post → Tasks 4–5. State store → Task 6. Diff → Task 7. scan/post two-mode CLI → Task 8. Claude-mediated drafting/approval + command → Task 9. Config/auth → Task 1. Error handling (auth/api/per-thread) → Tasks 2 + 8. Testing (unit + gated integration) → Tasks 1–8 + Task 10. Packaging/marketplace → Tasks 1 + 9. All spec sections map to a task.
- Deferred items (Word, auto-post, suggestions, Slack) intentionally have no task — correct for v1.

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". The two `> v1 simplification` notes are explicit scope cuts with rationale, not placeholders.

**Type consistency:** `Thread`/`Page` fields identical across Tasks 3–8. `post_reply(thread, text, page_id)` signature aligned in base (Task 5 Step 1), confluence (Task 5 Step 4), and caller (Task 8). `queue_new_or_updated(threads, seen)`, `State.mark_seen/save(now=)`, `ConfluenceClient.get/post`, `load_config`/`Config` all consistent between definition and use.
