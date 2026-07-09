import json
import pytest
from skills_builder.installer import Installer, InstallError, InstallResult


def _make_src(tmp_path, name="launch-announcements", body="body"):
    src = tmp_path / "build" / ".claude" / "skills" / name
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n{body}")
    return src


def _prov():
    return {"build_id": "b1", "installed_at": "2026-07-08T00:00:00Z", "tool_version": "0.1.0"}


def test_install_copies_skill_and_writes_provenance(tmp_path):
    src = _make_src(tmp_path)
    inst = Installer(skills_root=tmp_path / "skills")
    res = inst.install(src, "launch-announcements", _prov())
    assert isinstance(res, InstallResult)
    dest = tmp_path / "skills" / "launch-announcements"
    assert (dest / "SKILL.md").exists()
    prov = json.loads((dest / ".skills-builder.json").read_text())
    assert prov["build_id"] == "b1"
    assert res.overwritten is False


def test_is_installed_reflects_state(tmp_path):
    src = _make_src(tmp_path)
    inst = Installer(skills_root=tmp_path / "skills")
    assert inst.is_installed("launch-announcements") is False
    inst.install(src, "launch-announcements", _prov())
    assert inst.is_installed("launch-announcements") is True


def test_collision_without_overwrite_raises(tmp_path):
    src = _make_src(tmp_path)
    inst = Installer(skills_root=tmp_path / "skills")
    inst.install(src, "launch-announcements", _prov())
    with pytest.raises(InstallError):
        inst.install(src, "launch-announcements", _prov())


def test_overwrite_replaces_existing(tmp_path):
    src = _make_src(tmp_path)
    inst = Installer(skills_root=tmp_path / "skills")
    inst.install(src, "launch-announcements", _prov())
    res = inst.install(src, "launch-announcements", _prov(), overwrite=True)
    assert res.overwritten is True


def test_install_under_new_name_rewrites_frontmatter(tmp_path):
    src = _make_src(tmp_path, name="launch-announcements")
    inst = Installer(skills_root=tmp_path / "skills")
    inst.install(src, "launch-posts", _prov())
    installed = (tmp_path / "skills" / "launch-posts" / "SKILL.md").read_text()
    assert "name: launch-posts" in installed
    assert "name: launch-announcements" not in installed


def test_missing_source_skill_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    inst = Installer(skills_root=tmp_path / "skills")
    with pytest.raises(InstallError):
        inst.install(empty, "x", _prov())


def test_uninstall_removes_skill(tmp_path):
    src = _make_src(tmp_path)
    inst = Installer(skills_root=tmp_path / "skills")
    inst.install(src, "launch-announcements", _prov())
    inst.uninstall("launch-announcements")
    assert inst.is_installed("launch-announcements") is False
