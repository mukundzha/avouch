"""
Default configuration values for Scrut.
"""

DEFAULT_LIMITS = {
    "max_parameters": 5,
    "max_nesting": 4,
    "max_function_lines": 50,
    "max_class_lines": 200,
    "max_file_lines": 400,
    "max_complexity": 10,
    "max_boolean_conditions" : 5,
    "max_if_else_chain": 5,
    "max_local_variables": 15,
    "max_return_statements": 3,
    "max_lambda_nodes": 5,
    "max_large_comprehensions": 10,
}

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
}
