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
