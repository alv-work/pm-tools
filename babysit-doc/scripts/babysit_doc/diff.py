def queue_new_or_updated(threads, seen):
    out = []
    for t in threads:
        last = seen.get(t.id)
        if last is None or t.updated_at > last:
            out.append(t)
    return out
