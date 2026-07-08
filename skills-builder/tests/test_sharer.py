import zipfile
import pytest
from skills_builder.sharer import share_or_export, ShareResult, ShareError


def _make_skill(tmp_path, name="launch-announcements"):
    d = tmp_path / "src" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\nbody")
    return d


def test_export_zip_when_no_share_repo(tmp_path):
    src = _make_skill(tmp_path)
    downloads = tmp_path / "dl"
    res = share_or_export(src, "launch-announcements", share_repo=None, downloads=downloads)
    assert res.mode == "export"
    zf = zipfile.ZipFile(res.path)
    names = zf.namelist()
    assert "launch-announcements/SKILL.md" in names
    assert "launch-announcements/INSTALL.txt" in names


def test_missing_skill_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ShareError):
        share_or_export(empty, "x", share_repo=None, downloads=tmp_path / "dl")


def test_pr_flow_runs_git_and_gh_and_returns_url(tmp_path):
    src = _make_skill(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    cmds = []

    def runner(argv, cwd):
        cmds.append(argv)
        if argv[:2] == ["gh", "pr"]:
            return "https://github.com/team/marketplace/pull/42\n", 0, ""
        return "", 0, ""  # git --version, gh --version, and all git steps succeed

    res = share_or_export(src, "launch-announcements", share_repo=str(repo),
                          downloads=tmp_path / "dl", runner=runner)
    assert res.mode == "pr"
    assert res.url == "https://github.com/team/marketplace/pull/42"
    # skill was copied into the repo subdir
    assert (repo / "shared-skills" / "launch-announcements" / "SKILL.md").exists()
    # a branch was created and a PR opened
    assert ["git", "checkout", "-b", "skill/launch-announcements"] in cmds
    assert ["gh", "pr", "create", "--fill"] in cmds


def test_falls_back_to_export_when_tools_unavailable(tmp_path):
    src = _make_skill(tmp_path)

    def runner(argv, cwd):
        return "", 1, "not found"  # git/gh unavailable

    res = share_or_export(src, "launch-announcements", share_repo=str(tmp_path / "repo"),
                          downloads=tmp_path / "dl", runner=runner)
    assert res.mode == "export"


def test_git_failure_raises_share_error(tmp_path):
    src = _make_skill(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()

    def runner(argv, cwd):
        if argv[-1] == "--version":
            return "", 0, ""
        if argv[:2] == ["git", "push"]:
            return "", 1, "no remote configured"
        return "", 0, ""

    with pytest.raises(ShareError):
        share_or_export(src, "launch-announcements", share_repo=str(repo),
                        downloads=tmp_path / "dl", runner=runner)
