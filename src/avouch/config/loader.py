from pathlib import Path
import tomllib

from .default import DEFAULT_LIMITS

CONFIG_FILE = "avouch.toml"

DEFAULT_RULES = {
    "max_parameters": True,
    "max_nesting": True,
    "max_function_lines": True,
    "max_class_lines": True,
    "max_file_lines": True,
    "max_complexity": True,
    "max_boolean_conditions": True,
    "max_if_else_chain": True,
    "max_local_variables": True,
    "max_return_statements": True,
    "max_lambda_nodes": True,
    "max_large_comprehensions": True,
    "empty_except": True,
    "detect_duplicateb": True,
    "nested_function": True,
    "bare_except": True,
    "async_without_await": True,
    "mutable_default_args": True,
    "shell_true": True,
    "dynamic_code": True,
}

DEFAULT_IGNORE_PATHS = []

_load_cache = {}


def find_config_path(start=None):
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        candidate = parent / CONFIG_FILE
        if candidate.is_file():
            return candidate
    return None


def _validate_limits(user_limits):
    if not isinstance(user_limits, dict):
        raise ValueError(f"limits must be a table; got {type(user_limits).__name__}")
    for k, v in list(user_limits.items()):
        if k not in DEFAULT_LIMITS:
            continue
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"limits.{k} must be a positive integer; got {v!r}")
        if v <= 0:
            raise ValueError(f"limits.{k} must be a positive integer; got {v!r}")


def _validate_rules(user_rules):
    if not isinstance(user_rules, dict):
        raise ValueError(f"rules must be a table; got {type(user_rules).__name__}")
    for k, v in list(user_rules.items()):
        if k not in DEFAULT_RULES:
            continue
        if not isinstance(v, bool):
            raise ValueError(f"rules.{k} must be a boolean; got {v!r}")


def load_config(start=None):

    config_path = find_config_path(start)

    if config_path is None:
        return {"limits": DEFAULT_LIMITS.copy(), "rules": DEFAULT_RULES.copy(), "ignore_paths": DEFAULT_IGNORE_PATHS.copy(), "_config_path": None}

    stat = config_path.stat()

    key = (str(config_path.resolve()), stat.st_mtime_ns, stat.st_size)

    cached = _load_cache.get(key)

    if cached is not None:
        return cached

    try:
        with open(config_path, "rb") as file:
            config = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML: {exc}") from exc

    merged_config = {
        "limits": merge_limits(config.get("limits", {})),
        "rules": merge_rules(config.get("rules", {})),
        "ignore_paths": merge_ignore_paths(config.get("ignore_paths", [])),
        "_config_path": str(config_path.resolve()),
    }

    _load_cache[key] = merged_config

    return merged_config


def merge_limits(user_limits):

    _validate_limits(user_limits)

    merged_limits = DEFAULT_LIMITS.copy()

    for k, v in user_limits.items():
        if k in DEFAULT_LIMITS:
            merged_limits[k] = v

    return merged_limits

def merge_rules(user_rules):

    _validate_rules(user_rules)

    merged_rules = DEFAULT_RULES.copy()

    for k, v in user_rules.items():
        if k in DEFAULT_RULES:
            merged_rules[k] = v

    return merged_rules

def merge_ignore_paths(user_ignore_paths):

    if not isinstance(user_ignore_paths, list):
        raise ValueError("ignore_paths must be a list of strings")

    for i, p in enumerate(user_ignore_paths):
        if not isinstance(p, str):
            raise ValueError(f"ignore_paths[{i}] must be a string; got {p!r}")

    merged = DEFAULT_IGNORE_PATHS.copy()

    merged.extend(user_ignore_paths)

    return merged
