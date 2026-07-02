# babysit-doc — How to use

`babysit-doc` watches a Confluence page's comment threads. On each run it finds
the comments that are new or updated since you last looked, drafts a reply to
each one (using the full page as context), and shows you the drafts. Nothing is
posted to Confluence until you approve it.

It is **draft-only**: the tool never posts on its own. You approve, edit, or skip
every reply.

---

## 1. Prerequisites

- **Python 3.10+** on your machine (`python3 --version`). No pip packages needed —
  the tool uses only the standard library.
- A **Confluence Cloud** site and an account that can read the page and post
  comments on it.
- A **Confluence API token** (see next section).
- Internet access when you run it (it calls the Confluence REST API).

---

## 2. Install

From any Claude Code session:

```
/plugin marketplace add alv-work/pm-tools
/plugin install babysit-doc@pm-tools
```

Reload plugins if prompted. You now have the `/babysit-doc` command.

---

## 3. Configure credentials

The tool reads three values. Set them as environment variables **or** put them in
a config file — env vars win if both are present.

### Get an API token
1. Go to <https://id.atlassian.com/manage-profile/security/api-tokens>.
2. Create a token, copy it.

### Option A — environment variables
```bash
export CONFLUENCE_BASE_URL="https://<your-site>.atlassian.net/wiki"
export CONFLUENCE_EMAIL="you@example.com"
export CONFLUENCE_API_TOKEN="<the token you copied>"
```
`CONFLUENCE_BASE_URL` must end in `/wiki`. Put these in your shell profile so
they persist.

### Option B — config file
Create `~/.config/babysit-doc/config.json`:
```json
{
  "CONFLUENCE_BASE_URL": "https://<your-site>.atlassian.net/wiki",
  "CONFLUENCE_EMAIL": "you@example.com",
  "CONFLUENCE_API_TOKEN": "<the token you copied>"
}
```

If any value is missing, the tool tells you exactly which ones and where to set
them, and does nothing else.

---

## 4. Use it

```
/babysit-doc https://<your-site>.atlassian.net/wiki/spaces/ENG/pages/12345/My+Spec
```

You can pass a full page URL or just the numeric page id (`/babysit-doc 12345`).

**What happens:**
1. The tool fetches the page and its **open** comment threads (footer + inline),
   and keeps only threads that are new or have new replies since your last run.
2. For each one, Claude reads the comment in the context of the whole page and
   writes a draft reply, marking its confidence (high / low).
3. You see every draft with the original comment and a link. For each you can:
   **approve** (post as-is), **edit** (change the text, then post), or **skip**.
4. Only approved/edited replies are posted back to Confluence. Skipped threads
   come back next run so you don't lose them.

If there are no new comments, it says so and stops.

---

## 5. Watch a page continuously

Pair it with the `/loop` command to re-check on an interval:

```
/loop 10m /babysit-doc https://<your-site>.atlassian.net/wiki/spaces/ENG/pages/12345/My+Spec
```

This runs a fresh pass every 10 minutes. Each pass only surfaces genuinely new or
updated threads (state is remembered per page), so you won't see the same comment
twice unless it changes.

---

## 6. Safety notes

- **Draft-only.** The tool posts a reply only after you approve it in the session.
  There is no auto-post mode in this version.
- **Comment text is treated as untrusted data.** If a comment tries to instruct
  Claude to post, approve, or take an action, Claude is told to ignore it and
  surface it to you as an ordinary comment. Approval always comes from you.
- Replies post **under your account** (the one whose API token you configured),
  so review the wording before approving.

---

## 7. Run the CLI directly (optional)

The command wraps a small Python CLI you can also run yourself — handy for a first
smoke test:

```bash
# from the installed plugin dir; scripts live under scripts/
PYTHONPATH="scripts" python3 -m babysit_doc scan "<page-url-or-id>"
# → prints JSON: { "page": {id,title,url,text}, "threads": [ ...new/updated... ] }

PYTHONPATH="scripts" python3 -m babysit_doc post "<page-url-or-id>" "<thread_id>" "<footer|inline>" "your reply text"
# → posts one reply and marks that thread handled
```

State is stored per page at `~/.config/babysit-doc/state/<page-id>.json`.

---

## 8. Troubleshooting

- **"missing Confluence credentials: …"** — a value isn't set. Add it via env or
  the config file (section 3).
- **Auth rejected / 401 / 403** — wrong email/token, or the account can't see the
  page. Regenerate the token and confirm you can open the page in a browser.
- **"could not find a page id in: …"** — pass a URL that contains `/pages/<number>/`
  or just the numeric id.
- **It keeps prompting for permission to run** — the command allows `Bash`; approve
  it once, or add an allow rule in your Claude Code settings.
- **Replies look unstyled / no page text** — you're likely offline or the API
  returned an unexpected shape; the tool reports a clear error rather than crashing.

---

## 9. Limitations (this version)

- **Confluence Cloud only.** (MS Word / SharePoint via Microsoft Graph is planned.)
- Reads up to **100 top-level comments** per page (no pagination yet).
- No automatic **retry/backoff** on rate limits or transient 5xx — it reports and
  exits; just run it again.
- Handles **comment threads**, not inline *suggestions* (tracked-edit accept/reject).
