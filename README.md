# pm-tools

A Claude Code plugin marketplace of tools, plugins, and skills for PMs.

## Plugins

### read-md-plugin
Renders a generated markdown file as HTML in your browser — Medium-style serif reading layout, auto-built sidebar navigation, and a light/dark toggle. Built for the markdown that the Superpowers plugin writes under `docs/superpowers/`, but works on any `.md` file.

### babysit-doc
Watches a Confluence page's comment threads and drafts replies for you to approve before anything posts. Pair with `/loop` for continuous watching: `/loop 10m /babysit-doc <page-url>`. Needs `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`. See [babysit-doc/USAGE.md](babysit-doc/USAGE.md) for setup, the approval flow, and troubleshooting.

### skills-builder
A browser tool that lets non-technical PMs build, test, install, and share Claude skills without touching a terminal. `/skills-builder` starts a local server and opens a UI that walks you from idea → shaped questions → drafted skill → real playground test → one-click install. Underneath, a headless Claude session does the questioning and authoring. Needs the `claude` CLI logged in; Python stdlib only. See [skills-builder/USAGE.md](skills-builder/USAGE.md).

## Install

```
/plugin marketplace add alv-work/pm-tools
/plugin install read-md-plugin@pm-tools
```

Then reload plugins if prompted.

## Usage

```
/read-md                       # newest *.md under ./docs/superpowers/ in the current project
/read-md path/to/file.md       # a specific file
```

The command prints the source markdown path and the generated HTML path, and opens the HTML in your default browser.

## Requirements

- Python 3 (uses the standard library only — no pip installs)
- Internet on first view: fonts, the markdown parser (marked.js), and syntax highlighting (highlight.js) load from CDNs. Offline it falls back to a system serif and unhighlighted code — still readable.

## What it renders

- Serif body / sans headings, comfortable measure and line-height
- Sidebar table of contents auto-generated from `##`/`###` headings, with scroll-spy and breadcrumb
- Light/dark theme toggle, persisted; initial theme follows your OS setting
- Soft, syntax-highlighted code blocks; styled tables, blockquotes, and rules
