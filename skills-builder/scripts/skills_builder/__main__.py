"""CLI entrypoint: `python3 -m skills_builder serve` starts the local app.

Picks a free port, mints a per-launch session key, opens the browser, and prints
a JSON status line (with the URL as fallback) before serving forever.
"""
import json
import secrets
import sys
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from .engine import Engine
from .prompts import SYSTEM_PROMPT
from .server import App, make_server
from .store import Store

UI_DIR = Path(__file__).parent / "ui"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id():
    return uuid.uuid4().hex[:12]


def serve(host="127.0.0.1", port=0, open_browser=True):
    key = secrets.token_hex(24)
    app = App(
        store=Store(),
        engine=Engine(system_prompt=SYSTEM_PROMPT),
        clock=_now,
        id_gen=_new_id,
    )
    server = make_server(app, key=key, ui_dir=str(UI_DIR), host=host, port=port)
    actual_port = server.server_address[1]
    url = f"http://localhost:{actual_port}/?key={key}"
    print(json.dumps({
        "type": "server-started", "host": host, "port": actual_port, "url": url,
    }))
    sys.stdout.flush()
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "serve"
    if cmd == "serve":
        serve()
        return 0
    print("usage: skills_builder serve", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
