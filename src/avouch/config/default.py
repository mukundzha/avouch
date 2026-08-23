"""
Default configuration values for Avouch.
"""

from pathlib import Path
import tomllib

DEFAULT_LIMITS = {
    "max_parameters": 5,
    "max_nesting": 5,
    "max_function_lines": 300,
    "max_class_lines": 200,
    "max_file_lines": 1000,
    "max_complexity": 40,
    "max_boolean_conditions": 5,
    "max_if_chain": 5,
    "max_local_variables": 30,
    "max_return_statements": 6,
    "max_lambda_nodes": 10,
    "max_large_comprehensions": 40,
}


def load_limits():

    from avouch.config.loader import load_config

    return load_config()["limits"]