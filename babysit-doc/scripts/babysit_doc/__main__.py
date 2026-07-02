import json, sys
from datetime import datetime, timezone
from .config import load_config, ConfigError
from .confluence_client import ConfluenceClient, ClientError
from .sources.confluence import ConfluenceSource
from .state import State
from .diff import queue_new_or_updated


def _default_source(cfg):
    return ConfluenceSource(ConfluenceClient(cfg))


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv=None, source_factory=None, state_factory=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: babysit_doc scan <ref> | post <ref> <thread_id> <type> <text>", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]

    try:
        if source_factory:
            source = source_factory(None)
        else:
            cfg = load_config()
            source = _default_source(cfg)
    except (ConfigError, ClientError) as e:
        print(f"babysit-doc: {e}", file=sys.stderr)
        return 1

    make_state = state_factory or (lambda pid: State(pid))

    try:
        if cmd == "scan":
            if not rest:
                print("usage: babysit_doc scan <ref>", file=sys.stderr)
                return 2
            page = source.resolve(rest[0])
            state = make_state(page.id)
            queued = queue_new_or_updated(source.list_threads(page), state.seen)
            state.save(now=_now())
            print(json.dumps({
                "page": page.to_dict(),
                "threads": [t.to_dict() for t in queued],
            }, indent=2))
            return 0

        if cmd == "post":
            if len(rest) < 4:
                print("usage: babysit_doc post <ref> <thread_id> <type> <text>", file=sys.stderr)
                return 2
            ref, thread_id, ttype, text = rest[0], rest[1], rest[2], rest[3]
            page = source.resolve(ref)
            state = make_state(page.id)
            thread = next((t for t in source.list_threads(page) if t.id == thread_id), None)
            if thread is None:
                print(f"babysit-doc: thread {thread_id} not found", file=sys.stderr)
                return 1
            source.post_reply(thread, text, page.id)
            state.mark_seen(thread_id, thread.updated_at)
            state.save(now=_now())
            print(json.dumps({"posted": thread_id}))
            return 0

        print(f"babysit-doc: unknown command {cmd!r}", file=sys.stderr)
        return 2
    except ClientError as e:
        print(f"babysit-doc: {e}", file=sys.stderr)
        return 1
    except (KeyError, IndexError) as e:
        print(f"babysit-doc: unexpected data from Confluence: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
