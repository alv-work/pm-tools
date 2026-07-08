#!/usr/bin/env python3
"""A stand-in for the `claude` CLI used by integration tests.

Emits a canned stream-json sequence ending in a valid protocol turn, so the
real subprocess path in claude_cli.run_claude and the engine can be exercised
with zero API cost. Honors SKILLS_BUILDER_FAKE_MODE for a few scripted variants.
"""
import json
import os
import sys

MODE = os.environ.get("SKILLS_BUILDER_FAKE_MODE", "valid")
SESSION = os.environ.get("SKILLS_BUILDER_FAKE_SESSION", "fake-sess")

VALID_TURN = (
    "What should the skill help Claude do better?\n"
    "```json\n"
    '{"stage": "shape", "widget": {"type": "free_text", '
    '"question": "What should the skill help Claude do better?"}, "done": false}\n'
    "```"
)


def emit(events):
    for e in events:
        sys.stdout.write(json.dumps(e) + "\n")


if MODE == "crash":
    sys.stderr.write("fake claude: not logged in\n")
    sys.exit(1)

text = VALID_TURN if MODE == "valid" else "I forgot the protocol block."
emit([
    {"type": "system", "subtype": "init", "session_id": SESSION, "tools": []},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
    {"type": "result", "subtype": "success", "is_error": False,
     "result": text, "session_id": SESSION},
])
sys.exit(0)
