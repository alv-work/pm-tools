# read-md-plugin

A Claude Code plugin that renders a generated markdown file as HTML in your browser — Medium-style serif reading layout, auto-built sidebar navigation, and a light/dark toggle.

Built for the markdown that the Superpowers plugin writes under `docs/superpowers/`, but works on any `.md` file.

## Install

```
/plugin marketplace add alv-work/read-md-plugin
/plugin install read-md-plugin@avaibhav-tools
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
