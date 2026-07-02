import re, html
from .base import DocSource, Page, Thread

_ID_RE = re.compile(r"/pages/(\d+)")


def extract_page_id(ref):
    ref = ref.strip()
    if ref.isdigit():
        return ref
    m = _ID_RE.search(ref)
    if not m:
        raise ValueError(f"could not find a page id in: {ref}")
    return m.group(1)


def strip_tags(value):
    text = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(text).strip()


class ConfluenceSource(DocSource):
    def __init__(self, client):
        self._c = client

    def resolve(self, ref):
        pid = extract_page_id(ref)
        data = self._c.get(f"/api/v2/pages/{pid}", {"body-format": "storage"})
        body = (data.get("body", {}).get("storage", {}) or {}).get("value", "")
        base = re.sub(r"/wiki.*$", "/wiki", ref) if "/wiki" in ref else ""
        webui = (data.get("_links", {}) or {}).get("webui", "")
        url = (base + webui) if webui else ref
        return Page(id=pid, title=data.get("title", ""), url=url, text=strip_tags(body))

    def _paged(self, path):
        # v1: single page of up to 100; pagination deferred (noted in plan).
        data = self._c.get(path, {"body-format": "storage", "limit": 100})
        return data.get("results", [])

    def _thread_from(self, kind, top):
        tid = str(top["id"])
        children = self._paged(f"/api/v2/{kind}-comments/{tid}/children")
        chain = [top] + children
        parts, updated = [], top["version"]["createdAt"]
        for c in chain:
            parts.append(strip_tags(c["body"]["storage"]["value"]))
            updated = max(updated, c["version"]["createdAt"])
        anchor = None
        if kind == "inline":
            props = top.get("properties", {}) or {}
            anchor = props.get("inline-original-selection") or props.get("inlineOriginalSelection")
        return Thread(
            id=tid, type=kind, author=str(top["version"].get("authorId", "")),
            created_at=top["version"]["createdAt"], updated_at=updated,
            comment_text="\n\n".join(p for p in parts if p),
            permalink=(top.get("_links", {}) or {}).get("webui", ""), anchor=anchor,
        )

    def list_threads(self, page):
        threads = []
        for kind in ("footer", "inline"):
            for top in self._paged(f"/api/v2/pages/{page.id}/{kind}-comments"):
                threads.append(self._thread_from(kind, top))
        return threads

    def post_reply(self, thread, text):
        raise NotImplementedError  # Task 5
