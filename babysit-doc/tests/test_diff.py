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
