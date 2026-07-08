from skills_builder.prompts import (
    build_system_prompt, PROTOCOL_CONTRACT, _load_skill_body, _SKILL_PATH,
)


def test_system_prompt_includes_contract_and_authoring_guidance():
    sp = build_system_prompt()
    # machine contract present
    assert "```json" in sp
    assert "draft_review" in sp
    # authoring craft from the skill file present
    assert "Trigger" in sp or "trigger" in sp
    assert "kebab-case" in sp


def test_skill_file_exists_and_has_frontmatter_stripped():
    assert _SKILL_PATH.exists()
    body = _load_skill_body()
    assert not body.startswith("---")
    assert "How to author" in body


def test_missing_skill_file_falls_back_to_contract(tmp_path):
    body = _load_skill_body(tmp_path / "nope.md")
    assert body == ""
