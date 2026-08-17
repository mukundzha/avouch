import ast

_CACHE = {}


def walk(node):
    key = id(node)
    cached = _CACHE.get(key)
    if cached is None:
        cached = list(ast.walk(node))
        _CACHE[key] = cached
    return cached


def reset_walk_cache():
    _CACHE.clear()