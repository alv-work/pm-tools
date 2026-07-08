---
description: Open Skills Builder — a browser tool to build, test, and install Claude skills without a terminal
allowed-tools: Bash
---

Open the Skills Builder for the user. Do exactly this:

1. Start the local server in the background (it opens the browser itself and prints a `server-started` JSON line with the URL):

```
nohup env PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" python3 -m skills_builder serve >"${TMPDIR:-/tmp}/skills-builder.log" 2>&1 &
sleep 2
head -n 5 "${TMPDIR:-/tmp}/skills-builder.log"
```

2. Read the `url` from the printed JSON line. Tell the user their browser should have opened, and give them that URL as a fallback. Mention they can close this desktop app once the browser is open — the builder runs on its own local server until they stop it.

3. If the log shows an error about `claude` not being found or not logged in, tell the user to open a terminal, run `claude` once to log in, then run `/skills-builder` again.

Do not do anything else.
