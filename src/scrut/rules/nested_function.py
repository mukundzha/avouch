import ast

from scrut.utility.walk import walk


def analyze(function_node, limits):

    issues = []

    for node in walk(function_node):

        # Ignore everything except function definitions
        if not isinstance(node, ast.FunctionDef):
            continue

        # Ignore the function we're currently analyzing
        if node is function_node:
            continue

        # Any other FunctionDef is nested
        issues.append(
            {
                "rule": "SCR015",
                "severity": "WARNING",
                "message": "Nested function definition detected. Move the inner function to module level or extract into a separate function.",
            }
        )

    return issues