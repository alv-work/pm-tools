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


def test_post_with_too_few_args_returns_usage(capsys):
    rc = main(["post", "5", "100"], source_factory=lambda cfg: FakeSource())
    assert rc == 2
    err = capsys.readouterr().err
    assert "usage:" in err and "post" in err


def test_scan_with_no_args_returns_usage(capsys):
    rc = main(["scan"], source_factory=lambda cfg: FakeSource())
    assert rc == 2
    err = capsys.readouterr().err
    assert "usage:" in err and "scan" in err
