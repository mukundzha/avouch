from pathlib import Path
import tomllib

from .default import DEFAULT_LIMITS

CONFIG_FILE = "scrut.toml"


def load_config():

    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        return {"limits": DEFAULT_LIMITS}

    with open(config_path, "rb") as file:
        config = tomllib.load(file)

    user_limits = config.get("limits", {})

    merged_limits = merge_limits(user_limits)

    return {"limits": merged_limits}


def merge_limits(user_limits):

    merged_limits = DEFAULT_LIMITS.copy()

    merged_limits.update(user_limits)

    return merged_limits
