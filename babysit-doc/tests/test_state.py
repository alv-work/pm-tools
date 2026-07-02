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
