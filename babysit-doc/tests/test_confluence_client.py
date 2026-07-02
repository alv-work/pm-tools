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
