---
description: Render a generated markdown file as HTML in the browser (newest superpowers doc by default)
argument-hint: "[path/to/file.md]"
allowed-tools: Bash(python3:*)
---

Run the read-md renderer, passing along any path the user gave:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/read-md.py" $ARGUMENTS
```

Behavior:
- If `$ARGUMENTS` names a file, render that file.
- If empty, render the newest `*.md` under `./docs/superpowers/` in the current project.

Report the two `read-md:` output lines (the source md path and the generated html path) back to the user. Do not do anything else.
