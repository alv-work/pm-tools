"""Socket-level tests: start make_server and hit it with urllib."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from skills_builder.server import App, make_server
from skills_builder.store import Store


@pytest.fixture
def server(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<html>skills-builder</html>")
    app = App(store=Store(root=tmp_path / "builds"), engine=None,
              clock=lambda: "2026-07-08T00:00:00Z", id_gen=lambda: "b1")
    srv = make_server(app, key="secret", ui_dir=str(ui), port=0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read().decode()


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read().decode())


def test_api_requires_key(server):
    with pytest.raises(urllib.error.HTTPError) as ei:
        _get(f"{server}/api/builds")
    assert ei.value.code == 401


def test_api_with_key_lists_builds(server):
    status, body = _get(f"{server}/api/builds?key=secret")
    assert status == 200
    assert '"builds"' in body


def test_static_index_served_without_key(server):
    status, body = _get(f"{server}/")
    assert status == 200
    assert "skills-builder" in body


def test_create_build_via_post(server):
    status, body = _post(f"{server}/api/builds?key=secret", {"title": "T"})
    assert status == 201
    assert body["build"]["id"] == "b1"
