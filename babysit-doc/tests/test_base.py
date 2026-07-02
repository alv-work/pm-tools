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
