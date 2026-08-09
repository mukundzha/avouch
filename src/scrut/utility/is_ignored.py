import posixpath

def is_ignored(path, ignore_paths):
    """Return True when a repository-relative path is covered by an
    ignore path. Ignore paths match whole path components, so a
    directory ("tests") never shadows a sibling file ("tests.py").
    Matching is purely string-based — no filesystem access."""
    if not ignore_paths:
        return False

    normalized = [posixpath.normpath(p) for p in ignore_paths]

    if any(p == "." for p in normalized):
        return True

    path = posixpath.normpath(path)

    return any(path == p or path.startswith(p + "/") for p in normalized)