---
description: Watch a Confluence page's comment threads; draft replies for you to approve before posting
argument-hint: "<confluence-page-url-or-id>"
allowed-tools: Bash(python3:*)
---

You are babysitting a Confluence doc's comments. Do exactly this:

1. Scan for new/updated threads:

```
python3 -m babysit_doc scan "$ARGUMENTS"
```

Run it from the plugin's script dir so the package imports:
```
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" python3 -m babysit_doc scan "$ARGUMENTS"
```

2. Parse the JSON. `page.text` is the full doc; `threads[]` are the comments needing attention.

3. If `threads` is empty, tell the user "No new comments" and stop.

4. For EACH thread, using `page.text` as context and the thread's `comment_text` (and `anchor` if present):
   - Decide if it warrants a reply (a question, request, or point addressed to the author). Skip pure FYIs.
   - Draft a concise, professional reply in the author's voice.
   - Judge your confidence: HIGH if the doc clearly supports the answer, LOW if you're guessing or it needs a human decision.

5. Present every draft to the user together, one block each:
   `[thread id] · confidence · author` / the comment / your draft. Flag LOW ones clearly.

6. Ask the user to approve, edit, or skip each. Do NOT post anything yet.

7. For each APPROVED (or edited) draft, post it:

```
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" python3 -m babysit_doc post "$ARGUMENTS" "<thread_id>" "<type>" "<final_text>"
```

Use the thread's `id` and `type` from the scan JSON. Report which threads posted.

Never post a reply the user did not approve. Never auto-post.
