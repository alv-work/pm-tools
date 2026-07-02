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
        self.base_url = "https://acme.atlassian.net/wiki"
        self.calls = []  # capture (path, params) per call
    def get(self, path, params=None):
        self.calls.append((path, params))
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
    assert t.comment_text == "Can we cut scope?\n\nAgreed"
    assert t.updated_at == "2026-07-01T12:00:00Z"   # latest reply wins
    assert t.permalink.startswith("https://acme.atlassian.net/wiki")


def test_resolve_bare_id_produces_absolute_url():
    page_id = "5"
    responses = {
        f"/api/v2/pages/{page_id}": {
            "title": "My Spec",
            "body": {"storage": {"value": "<p>Some content</p>"}},
            "_links": {"webui": "/spaces/ENG/pages/5/Spec"}
        }
    }
    src = ConfluenceSource(FakeClient(responses))
    page = src.resolve("5")
    assert page.url.startswith("https://acme.atlassian.net/wiki")


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


def test_list_threads_filters_inline_to_open_only():
    page_id = "5"
    responses = {
        f"/api/v2/pages/{page_id}/footer-comments": {"results": [], "_links": {}},
        f"/api/v2/pages/{page_id}/inline-comments": {"results": [], "_links": {}},
    }
    client = FakeClient(responses)
    src = ConfluenceSource(client)
    page = type("P", (), {"id": page_id})()
    src.list_threads(page)

    # assert inline call included resolution-status=open
    inline_call = [c for c in client.calls if "inline-comments" in c[0]][0]
    assert inline_call[1].get("resolution-status") == "open"

    # assert footer call did NOT include resolution-status
    footer_call = [c for c in client.calls if "footer-comments" in c[0]][0]
    assert "resolution-status" not in (footer_call[1] or {})
