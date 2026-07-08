"""HTTP server: an injectable `App` core plus a stdlib request handler.

`App` owns all routing logic and returns `(status, dict)` so it can be unit
tested with a fake engine and a temp store, no sockets involved. `make_server`
wraps it in a `ThreadingHTTPServer` that gates `/api/*` behind a per-launch
session key and serves the static UI from disk. Binds 127.0.0.1 only.
"""
import http.server
import json
import mimetypes
import urllib.parse
from dataclasses import asdict
from pathlib import Path

from . import flow
from .engine import EngineError
from .installer import InstallError
from .sharer import ShareError
from .store import StoreError

TOOL_VERSION = "0.1.0"

# Map engine failure kinds to HTTP status codes; the UI keys its error cards off `kind`.
_ERROR_STATUS = {
    "timeout": 504,
    "crash": 502,
    "protocol": 422,
    "setup": 424,
    "unknown": 500,
}


class App:
    def __init__(self, store, engine, clock, id_gen, playground=None, installer=None, sharer=None):
        self._store = store
        self._engine = engine
        self._clock = clock
        self._id_gen = id_gen
        self._playground = playground
        self._installer = installer
        self._sharer = sharer

    # ---- routes ---------------------------------------------------------

    def list_builds(self):
        return 200, {"builds": [asdict(m) for m in self._store.list()]}

    def create_build(self, body):
        build_id = self._id_gen()
        title = (body or {}).get("title") or "Untitled skill"
        meta = self._store.create(build_id, now=self._clock(), title=title)
        return 201, {"build": asdict(meta)}

    def get_build(self, build_id):
        try:
            meta = self._store.load(build_id)
        except StoreError:
            return 404, {"error": {"kind": "not_found", "message": "No such build."}}
        return 200, {"build": asdict(meta), "transcript": self._store.read_transcript(build_id)}

    def post_message(self, build_id, body):
        try:
            meta = self._store.load(build_id)
        except StoreError:
            return 404, {"error": {"kind": "not_found", "message": "No such build."}}

        body = body or {}
        if body.get("choice_id") is not None:
            display, prompt = self._resolve_choice(build_id, body["choice_id"])
        else:
            display = prompt = str(body.get("text", "")).strip()
        if not prompt:
            return 400, {"error": {"kind": "bad_request", "message": "Empty message."}}

        self._store.append_transcript(build_id, {"role": "user", "text": display})

        try:
            result = self._engine.turn(prompt, session_id=meta.session_id)
        except EngineError as e:
            return _ERROR_STATUS.get(e.kind, 500), {
                "error": {"kind": e.kind, "message": str(e), "detail": e.detail}
            }

        turn = result.turn
        meta.session_id = result.session_id or meta.session_id
        # flow is authoritative: accept the model's proposed stage only if the move is legal
        if turn.stage != meta.stage and flow.can_transition(meta.stage, turn.stage):
            meta.stage = turn.stage
        name = (turn.skill_preview or {}).get("name")
        if name:
            meta.skill_name = name
            if meta.title == "Untitled skill":
                meta.title = (turn.skill_preview or {}).get("description") or name
        meta.updated_at = self._clock()
        self._store.save(meta)

        if turn.draft and meta.skill_name:
            self._store.write_draft(build_id, meta.skill_name, turn.draft)

        entry = self._turn_to_entry(turn, meta.stage)
        self._store.append_transcript(build_id, entry)
        return 200, {"turn": entry, "build": asdict(meta)}

    def post_test_message(self, build_id, body):
        try:
            meta = self._store.load(build_id)
        except StoreError:
            return 404, {"error": {"kind": "not_found", "message": "No such build."}}
        if not meta.skill_name:
            return 400, {"error": {"kind": "no_draft", "message": "Nothing to test yet."}}

        message = str((body or {}).get("text", "")).strip()
        if not message:
            return 400, {"error": {"kind": "bad_request", "message": "Empty message."}}

        result = self._playground.run(
            self._store.build_dir(build_id), meta.skill_name, message,
            session_id=meta.test_session_id,
        )
        if result.is_error:
            return 502, {"error": {"kind": "crash", "message": "The test run failed.",
                                   "detail": result.error_text}}
        meta.test_session_id = result.session_id or meta.test_session_id
        meta.updated_at = self._clock()
        self._store.save(meta)
        return 200, {
            "reply": result.reply,
            "activated": result.activated,
            "denied_tools": result.denied_tools,
        }

    def post_install(self, build_id, body):
        try:
            meta = self._store.load(build_id)
        except StoreError:
            return 404, {"error": {"kind": "not_found", "message": "No such build."}}
        if not meta.skill_name:
            return 400, {"error": {"kind": "no_draft", "message": "Nothing to install yet."}}

        body = body or {}
        name = (body.get("name") or meta.skill_name).strip()
        overwrite = bool(body.get("overwrite"))
        src = self._store.draft_path(build_id, meta.skill_name).parent
        provenance = {
            "build_id": build_id,
            "skill_name": name,
            "installed_at": self._clock(),
            "tool_version": TOOL_VERSION,
        }
        try:
            result = self._installer.install(src, name, provenance, overwrite=overwrite)
        except InstallError as e:
            kind = "collision" if "already installed" in str(e) else "install_failed"
            status = 409 if kind == "collision" else 400
            return status, {"error": {"kind": kind, "message": str(e)}}

        meta.skill_name = name
        meta.status = "installed"
        if flow.can_transition(meta.stage, "use"):
            meta.stage = "use"
        meta.updated_at = self._clock()
        self._store.save(meta)
        return 200, {
            "installed": {"name": result.name, "path": result.path, "overwritten": result.overwritten},
            "build": asdict(meta),
        }

    def post_share(self, build_id, body):
        try:
            meta = self._store.load(build_id)
        except StoreError:
            return 404, {"error": {"kind": "not_found", "message": "No such build."}}
        if not meta.skill_name:
            return 400, {"error": {"kind": "no_draft", "message": "Nothing to share yet."}}

        skill_dir = self._store.draft_path(build_id, meta.skill_name).parent
        try:
            result = self._sharer(skill_dir, meta.skill_name)
        except ShareError as e:
            return 502, {"error": {"kind": "share_failed", "message": str(e)}}

        meta.status = "shared"
        meta.updated_at = self._clock()
        self._store.save(meta)
        return 200, {"mode": result.mode, "url": result.url, "path": result.path,
                     "build": asdict(meta)}

    # ---- helpers --------------------------------------------------------

    def _turn_to_entry(self, turn, stage):
        widget = None
        if turn.widget:
            widget = {
                "type": turn.widget.type,
                "question": turn.widget.question,
                "options": turn.widget.options,
                "allow_free_text": turn.widget.allow_free_text,
            }
        return {
            "role": "assistant",
            "chat_text": turn.chat_text,
            "stage": stage,
            "widget": widget,
            "skill_preview": turn.skill_preview,
            "draft": turn.draft,
            "done": turn.done,
        }

    def _resolve_choice(self, build_id, choice_id):
        for entry in reversed(self._store.read_transcript(build_id)):
            if entry.get("role") == "assistant" and entry.get("widget"):
                for opt in entry["widget"].get("options", []):
                    if opt["id"] == choice_id:
                        return opt["label"], f"I choose: {opt['label']}"
        return choice_id, f"I choose: {choice_id}"


def make_server(app, key, ui_dir, host="127.0.0.1", port=0):
    ui_root = Path(ui_dir).resolve()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # keep the console quiet; the command prints its own status line

        def _key_ok(self):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            k = (params.get("key") or [None])[0] or self.headers.get("X-Session-Key")
            return k == key

        def _route(self):
            return urllib.parse.urlparse(self.path).path

        def _send_json(self, status, obj):
            data = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, ValueError):
                return {}

        def do_GET(self):
            path = self._route()
            if path.startswith("/api/"):
                if not self._key_ok():
                    return self._send_json(401, {"error": {"kind": "auth", "message": "bad key"}})
                return self._api_get(path)
            return self._serve_static(path)

        def do_POST(self):
            path = self._route()
            if not path.startswith("/api/"):
                return self._send_json(404, {"error": {"kind": "not_found"}})
            if not self._key_ok():
                return self._send_json(401, {"error": {"kind": "auth", "message": "bad key"}})
            body = self._read_body()
            if path == "/api/builds":
                return self._send_json(*app.create_build(body))
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[1] == "builds" and parts[3] == "message":
                return self._send_json(*app.post_message(parts[2], body))
            if len(parts) == 5 and parts[1] == "builds" and parts[3:] == ["test", "message"]:
                return self._send_json(*app.post_test_message(parts[2], body))
            if len(parts) == 4 and parts[1] == "builds" and parts[3] == "install":
                return self._send_json(*app.post_install(parts[2], body))
            if len(parts) == 4 and parts[1] == "builds" and parts[3] == "share":
                return self._send_json(*app.post_share(parts[2], body))
            return self._send_json(404, {"error": {"kind": "not_found"}})

        def _api_get(self, path):
            if path == "/api/builds":
                return self._send_json(*app.list_builds())
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[1] == "builds":
                return self._send_json(*app.get_build(parts[2]))
            return self._send_json(404, {"error": {"kind": "not_found"}})

        def _serve_static(self, path):
            if path in ("/", ""):
                path = "/index.html"
            fp = (ui_root / path.lstrip("/")).resolve()
            try:
                fp.relative_to(ui_root)
            except ValueError:
                return self._send_json(403, {"error": {"kind": "forbidden"}})
            if not fp.is_file():
                return self._send_json(404, {"error": {"kind": "not_found"}})
            ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            data = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return http.server.ThreadingHTTPServer((host, port), Handler)
