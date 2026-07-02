import json
from dataclasses import dataclass
from pathlib import Path

KEYS = ("CONFLUENCE_BASE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN")
CONFIG_FILE = Path.home() / ".config" / "babysit-doc" / "config.json"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    base_url: str
    email: str
    token: str


def _from_file():
    if CONFIG_FILE.is_file():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError as e:
            raise ConfigError(f"invalid JSON in {CONFIG_FILE}: {e}")
    return {}


def load_config(env=None):
    import os
    env = os.environ if env is None else env
    file_vals = _from_file()
    vals = {k: env.get(k) or file_vals.get(k) for k in KEYS}
    missing = [k for k in KEYS if not vals[k]]
    if missing:
        raise ConfigError(
            "missing Confluence credentials: " + ", ".join(missing)
            + f"\nset them as env vars or in {CONFIG_FILE}"
        )
    return Config(vals["CONFLUENCE_BASE_URL"].rstrip("/"),
                  vals["CONFLUENCE_EMAIL"], vals["CONFLUENCE_API_TOKEN"])
