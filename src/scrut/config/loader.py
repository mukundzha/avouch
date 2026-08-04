from pathlib import Path
import tomllib

from .default import DEFAULT_LIMITS, DEFAULT_RULES

CONFIG_FILE = "scrut.toml"


def load_config():

    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        return {"limits": DEFAULT_LIMITS, "rules": DEFAULT_RULES}

    with open(config_path, "rb") as file:
        config = tomllib.load(file)

    user_limits = config.get("limits", {})

    merged_limits = merge_limits(user_limits)

    user_rules = config.get("rules", {})

    merged_rules = {**DEFAULT_RULES, **user_rules}

    return {"limits": merged_limits, "rules": merged_rules}


def merge_limits(user_limits):

    merged_limits = DEFAULT_LIMITS.copy()

    merged_limits.update(user_limits)

    return merged_limits
