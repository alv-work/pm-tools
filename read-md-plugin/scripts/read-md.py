#!/usr/bin/env python3
"""Render a markdown file to HTML and open it in the browser.

Usage: read-md.py [PATH]
  PATH given  -> render that file.
  PATH absent -> render the newest *.md under ./docs/superpowers/.
"""
import base64
import glob
import json
import os
import sys
import tempfile
import webbrowser

SEARCH_GLOB = "docs/superpowers/**/*.md"

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE_HTML__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@400;500;600;700&display=swap">
<link id="hl-light" rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/styles/github.min.css">
<link id="hl-dark" rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/styles/github-dark.min.css">
<script>
  // Set theme before first paint to avoid a flash.
  (function () {
    var t = null;
    try { t = localStorage.getItem("read-md-theme"); } catch (e) {}
    if (!t) t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.dataset.theme = t;
    var l = document.getElementById("hl-light"), d = document.getElementById("hl-dark");
    if (l) l.disabled = (t === "dark");
    if (d) d.disabled = (t !== "dark");
  })();
</script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release/build/highlight.min.js"></script>
<style>
  :root, [data-theme="light"] {
    --bg: #ffffff; --fg: #1c1c1c; --muted: #6b7280; --faint: #9aa0a8;
    --rule: #ececec; --sidebar-bg: #fbfbfa; --code-bg: #f6f4ef;
    --accent: #2f855a; --link: #1b64c4; --quote: #4a4a4a; --active-bg: #f0efec;
  }
  [data-theme="dark"] {
    --bg: #0f0f0f; --fg: #e9e6df; --muted: #8f8f8f; --faint: #6a6a6a;
    --rule: #262626; --sidebar-bg: #141414; --code-bg: #1b1b1b;
    --accent: #4ade80; --link: #7db1ff; --quote: #b8b4ac; --active-bg: #1e1e1e;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: "Source Serif 4", Charter, "Iowan Old Style", Georgia, serif;
    -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
    font-optical-sizing: auto;
  }

  /* layout */
  .sidebar {
    position: fixed; top: 0; left: 0; width: 288px; height: 100vh;
    background: var(--sidebar-bg); border-right: 1px solid var(--rule);
    overflow-y: auto; padding: 26px 20px 40px; z-index: 30;
    transition: transform .22s ease;
  }
  .main { margin-left: 288px; min-height: 100vh; }
  .topbar {
    position: sticky; top: 0; height: 56px; z-index: 20;
    display: flex; align-items: center; gap: 14px;
    padding: 0 26px; background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: saturate(1.2) blur(8px); border-bottom: 1px solid var(--rule);
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .crumb { font-size: 13px; color: var(--muted); flex: 1; min-width: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .crumb b { color: var(--fg); font-weight: 600; }
  .menu { display: none; background: none; border: 0; font-size: 20px;
    color: var(--fg); cursor: pointer; padding: 4px; }
  .theme {
    font-family: inherit; font-size: 12px; letter-spacing: .04em; font-weight: 500;
    text-transform: uppercase; color: var(--muted); background: none;
    border: 1px solid var(--rule); border-radius: 999px; padding: 6px 13px;
    cursor: pointer; transition: color .15s, border-color .15s;
  }
  .theme:hover { color: var(--fg); border-color: var(--faint); }

  /* sidebar contents */
  .brand { font-family: Inter, sans-serif; font-size: 15px; font-weight: 700;
    color: var(--fg); letter-spacing: -0.01em; margin: 2px 0 22px; padding: 0 8px;
    line-height: 1.3; }
  .toc { display: flex; flex-direction: column; font-family: Inter, sans-serif; }
  .toc-item {
    display: flex; gap: 12px; align-items: baseline;
    padding: 7px 10px; border-radius: 8px; text-decoration: none;
    color: var(--muted); font-size: 14px; line-height: 1.35;
    transition: background .12s, color .12s;
  }
  .toc-item .num { flex: none; width: 14px; text-align: center; font-size: 12px;
    color: var(--faint); font-variant-numeric: tabular-nums; }
  .toc-item.lvl3 { padding-left: 14px; font-size: 13.5px; }
  .toc-item.lvl3 .num::before { content: "\2022"; color: var(--faint); }
  .toc-item:hover { color: var(--fg); background: var(--active-bg); }
  .toc-item.active { color: var(--fg); font-weight: 600; background: var(--active-bg); }
  .toc-item.active .num { color: var(--accent); }
  .toc-empty { color: var(--faint); font-size: 13px; padding: 8px 10px; }

  /* article */
  .doc { max-width: 44rem; margin: 0 auto; padding: 56px 40px 160px;
    font-size: 20px; line-height: 1.75; }
  .doc > *:first-child { margin-top: 0; }
  p, ul, ol, blockquote, pre, table { margin: 0 0 1.5rem; }
  h1, h2, h3, h4, h5, h6 {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: var(--fg); line-height: 1.2; letter-spacing: -0.02em; font-weight: 700;
    scroll-margin-top: 74px;
  }
  h1 { font-size: 2.6rem; margin: 0 0 0.5em; letter-spacing: -0.03em; }
  h2 { font-size: 1.85rem; margin: 2.6rem 0 0.7rem; padding-top: 0.4rem; }
  h3 { font-size: 1.35rem; margin: 2rem 0 0.5rem; }
  h4 { font-size: 1.12rem; margin: 1.8rem 0 0.4rem; }
  h5, h6 { font-size: 0.95rem; margin: 1.6rem 0 0.4rem; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.06em; }
  a { color: var(--link); text-decoration: underline; text-decoration-thickness: 1px;
    text-underline-offset: 2px; text-decoration-color: color-mix(in srgb, var(--link) 40%, transparent); }
  a:hover { text-decoration-color: var(--link); }
  strong { font-weight: 600; }
  em { font-style: italic; }
  ul, ol { padding-left: 1.4em; }
  li { margin: 0.4rem 0; padding-left: 0.2em; }
  li::marker { color: var(--muted); }
  blockquote { margin-left: 0; padding: 0.3rem 0 0.3rem 1.4rem;
    border-left: 3px solid var(--accent); color: var(--quote); font-style: italic; }
  blockquote p { margin-bottom: 0.5rem; }
  blockquote > *:last-child { margin-bottom: 0; }
  code { font-family: "SF Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
    font-size: 0.85em; background: var(--code-bg); padding: 0.15em 0.4em;
    border-radius: 5px; border: 1px solid var(--rule); }
  pre { background: var(--code-bg); border: 1px solid var(--rule); border-radius: 12px;
    padding: 1.1rem 1.25rem; overflow-x: auto; line-height: 1.55; }
  pre code { background: none; border: 0; padding: 0; font-size: 0.8em; }
  hr { border: 0; text-align: center; margin: 3rem 0; }
  hr::before { content: "* * *"; letter-spacing: 0.8em; color: var(--muted); font-size: 1.2rem; }
  img { max-width: 100%; height: auto; border-radius: 8px; }
  table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid var(--rule); padding: 0.5rem 0.8rem; text-align: left; }
  th { background: var(--code-bg); font-family: Inter, sans-serif; font-weight: 600; }
  table tr:nth-child(even) td { background: color-mix(in srgb, var(--code-bg) 45%, transparent); }

  .scrim { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 25; }

  @media (max-width: 1024px) {
    .sidebar { transform: translateX(-100%); box-shadow: 0 0 40px rgba(0,0,0,.18); }
    .main { margin-left: 0; }
    .menu { display: block; }
    body.nav-open .sidebar { transform: none; }
    body.nav-open .scrim { display: block; }
  }
  @media (max-width: 640px) {
    .doc { font-size: 18px; padding: 36px 20px 100px; }
    h1 { font-size: 2.1rem; }
  }
</style>
</head>
<body>
<aside class="sidebar" id="sidebar">
  <div class="brand" id="brand">Contents</div>
  <nav class="toc" id="toc"></nav>
</aside>
<div class="scrim" id="scrim"></div>
<div class="main">
  <header class="topbar">
    <button class="menu" id="menu" aria-label="Toggle navigation">&#9776;</button>
    <div class="crumb" id="crumb"></div>
    <button class="theme" id="theme">Dark</button>
  </header>
  <article class="doc" id="content">Rendering&hellip;</article>
</div>

<script id="md" type="application/base64">__MD_B64__</script>
<script>
(function () {
  var root = document.documentElement;
  var hlLight = document.getElementById("hl-light");
  var hlDark = document.getElementById("hl-dark");
  var themeBtn = document.getElementById("theme");

  function applyTheme(t) {
    root.dataset.theme = t;
    themeBtn.textContent = (t === "dark") ? "Light" : "Dark";
    hlLight.disabled = (t === "dark");
    hlDark.disabled = (t !== "dark");
    try { localStorage.setItem("read-md-theme", t); } catch (e) {}
  }
  // Theme already set in <head> to avoid a flash; just sync the button label.
  applyTheme(root.dataset.theme === "dark" ? "dark" : "light");
  themeBtn.addEventListener("click", function () {
    applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
  });

  // decode + render markdown
  var b64 = document.getElementById("md").textContent.trim();
  var bytes = Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); });
  var md = new TextDecoder("utf-8").decode(bytes);
  var content = document.getElementById("content");
  content.innerHTML = marked.parse(md);
  if (window.hljs) content.querySelectorAll("pre code").forEach(function (el) { hljs.highlightElement(el); });

  // title + sidebar brand from first H1
  var h1 = content.querySelector("h1");
  var docTitle = (h1 ? h1.textContent : __TITLE_JSON__).trim();
  document.title = docTitle;
  document.getElementById("brand").textContent = docTitle;

  // build TOC from H2/H3
  var used = {};
  function slug(t) {
    var s = t.toLowerCase().trim().replace(/[^\w\s-]/g, "").replace(/[\s_]+/g, "-").replace(/^-+|-+$/g, "");
    if (!s) s = "section";
    if (used[s] != null) { used[s]++; s = s + "-" + used[s]; } else { used[s] = 0; }
    return s;
  }
  var heads = Array.prototype.slice.call(content.querySelectorAll("h2, h3"));
  var toc = document.getElementById("toc");
  var links = {};
  var n = 0;
  heads.forEach(function (h) {
    if (!h.id) h.id = slug(h.textContent);
    var lvl = (h.tagName === "H2") ? 2 : 3;
    if (lvl === 2) n++;
    var a = document.createElement("a");
    a.href = "#" + h.id;
    a.className = "toc-item lvl" + lvl;
    a.dataset.target = h.id;
    var num = document.createElement("span"); num.className = "num";
    if (lvl === 2) num.textContent = n;
    var txt = document.createElement("span"); txt.className = "txt";
    txt.textContent = h.textContent;
    a.appendChild(num); a.appendChild(txt);
    toc.appendChild(a);
    links[h.id] = a;
  });
  if (!heads.length) {
    var e = document.createElement("div"); e.className = "toc-empty";
    e.textContent = "No sections"; toc.appendChild(e);
  }

  function setActive(id) {
    Object.keys(links).forEach(function (k) { links[k].classList.remove("active"); });
    var a = links[id];
    if (a) {
      a.classList.add("active");
      document.getElementById("crumb").innerHTML =
        "<b></b> / <span></span>";
      var c = document.getElementById("crumb");
      c.querySelector("b").textContent = docTitle;
      c.querySelector("span").textContent = a.querySelector(".txt").textContent;
    }
  }
  document.getElementById("crumb").innerHTML = "";
  var crumbB = document.createElement("b");
  crumbB.textContent = docTitle;
  document.getElementById("crumb").appendChild(crumbB);

  // scroll-spy
  if (heads.length && "IntersectionObserver" in window) {
    var visible = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.isIntersecting; });
      for (var i = 0; i < heads.length; i++) {
        if (visible[heads[i].id]) { setActive(heads[i].id); return; }
      }
    }, { rootMargin: "-72px 0px -70% 0px", threshold: 0 });
    heads.forEach(function (h) { obs.observe(h); });
  }

  // mobile nav
  var body = document.body;
  document.getElementById("menu").addEventListener("click", function () { body.classList.toggle("nav-open"); });
  document.getElementById("scrim").addEventListener("click", function () { body.classList.remove("nav-open"); });
  toc.addEventListener("click", function (ev) { if (ev.target.closest(".toc-item")) body.classList.remove("nav-open"); });
})();
</script>
</body>
</html>
"""


def resolve_target(arg):
    if arg:
        path = os.path.abspath(os.path.expanduser(arg))
        if not os.path.isfile(path):
            sys.exit(f"read-md: file not found: {arg}")
        return path
    matches = glob.glob(SEARCH_GLOB, recursive=True)
    if not matches:
        sys.exit(
            "read-md: no markdown found under ./docs/superpowers/.\n"
            "Pass a path explicitly: read-md.py path/to/file.md"
        )
    return os.path.abspath(max(matches, key=os.path.getmtime))


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    target = resolve_target(arg)

    with open(target, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    title = os.path.basename(target)
    html = (
        PAGE.replace("__MD_B64__", b64)
        .replace("__TITLE_HTML__", title)
        .replace("__TITLE_JSON__", json.dumps(title))
    )

    fd, out = tempfile.mkstemp(prefix="read-md-", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)

    webbrowser.open(f"file://{out}")
    print(f"read-md: opened {target}")
    print(f"read-md: html -> {out}")


if __name__ == "__main__":
    main()
