from pathlib import Path
import tomllib

from .default import DEFAULT_LIMITS

CONFIG_FILE = "scrut.toml"

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
}


def load_config():

    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        return {"limits": DEFAULT_LIMITS, "rules": DEFAULT_RULES}

    with open(config_path, "rb") as file:
        config = tomllib.load(file)

    user_limits = config.get("limits", {})
    user_rules = config.get("rules", {})

    merged_limits = merge_limits(user_limits)

    return {"limits": merged_limits , "rules": merge_rules(user_rules) }


def merge_limits(user_limits):

    merged_limits = DEFAULT_LIMITS.copy()

    merged_limits.update(user_limits)

    return merged_limits

def merge_rules(user_rules):

    merged_rules = DEFAULT_RULES.copy()

    merged_rules.update(user_rules)

    return merged_rules

