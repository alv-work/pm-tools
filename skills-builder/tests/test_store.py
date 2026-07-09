import pytest
from skills_builder.store import Store, BuildMeta, StoreError


def test_create_and_load_round_trips(tmp_path):
    s = Store(root=tmp_path)
    meta = s.create("b1", now="2026-07-08T00:00:00Z", title="Launch posts")
    assert meta.id == "b1"
    assert meta.stage == "idea"
    assert meta.status == "draft"
    loaded = s.load("b1")
    assert loaded.title == "Launch posts"
    assert loaded.created_at == "2026-07-08T00:00:00Z"


def test_create_duplicate_raises(tmp_path):
    s = Store(root=tmp_path)
    s.create("b1", now="t")
    with pytest.raises(StoreError):
        s.create("b1", now="t")


def test_load_missing_raises(tmp_path):
    s = Store(root=tmp_path)
    with pytest.raises(StoreError):
        s.load("nope")


def test_save_updates_fields(tmp_path):
    s = Store(root=tmp_path)
    meta = s.create("b1", now="t")
    meta.stage = "shape"
    meta.skill_name = "launch-announcements"
    meta.session_id = "sess-7"
    meta.updated_at = "t2"
    s.save(meta)
    reloaded = s.load("b1")
    assert reloaded.stage == "shape"
    assert reloaded.skill_name == "launch-announcements"
    assert reloaded.session_id == "sess-7"


def test_list_sorted_by_updated_desc_and_ignores_junk(tmp_path):
    s = Store(root=tmp_path)
    a = s.create("a", now="t"); a.updated_at = "2026-07-01"; s.save(a)
    b = s.create("b", now="t"); b.updated_at = "2026-07-05"; s.save(b)
    (tmp_path / "not-a-build").mkdir()
    ids = [m.id for m in s.list()]
    assert ids == ["b", "a"]


def test_transcript_append_and_read(tmp_path):
    s = Store(root=tmp_path)
    s.create("b1", now="t")
    s.append_transcript("b1", {"role": "user", "text": "hi"})
    s.append_transcript("b1", {"role": "assistant", "text": "hello"})
    entries = s.read_transcript("b1")
    assert [e["role"] for e in entries] == ["user", "assistant"]


def test_write_draft_creates_project_skill_tree(tmp_path):
    s = Store(root=tmp_path)
    s.create("b1", now="t")
    path = s.write_draft("b1", "launch-announcements", "---\nname: launch-announcements\n---\nbody")
    assert path == s.draft_path("b1", "launch-announcements")
    assert path.read_text().startswith("---")
    # discovered as a project skill: <build>/.claude/skills/<name>/SKILL.md
    assert path.parts[-3:] == ("skills", "launch-announcements", "SKILL.md")
