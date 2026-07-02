import pytest
from babysit_doc.config import load_config, Config, ConfigError


def test_loads_from_env():
    env = {
        "CONFLUENCE_BASE_URL": "https://acme.atlassian.net/wiki",
        "CONFLUENCE_EMAIL": "me@acme.com",
        "CONFLUENCE_API_TOKEN": "tok",
    }
    cfg = load_config(env)
    assert cfg == Config("https://acme.atlassian.net/wiki", "me@acme.com", "tok")


def test_strips_trailing_slash_on_base_url():
    env = {
        "CONFLUENCE_BASE_URL": "https://acme.atlassian.net/wiki/",
        "CONFLUENCE_EMAIL": "me@acme.com",
        "CONFLUENCE_API_TOKEN": "tok",
    }
    assert load_config(env).base_url == "https://acme.atlassian.net/wiki"


def test_missing_keys_lists_all_of_them():
    with pytest.raises(ConfigError) as e:
        load_config({})
    msg = str(e.value)
    assert "CONFLUENCE_BASE_URL" in msg
    assert "CONFLUENCE_EMAIL" in msg
    assert "CONFLUENCE_API_TOKEN" in msg
