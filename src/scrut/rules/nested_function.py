import ast


def analyze(function_node, limits):

    issues = []

    for node in ast.walk(function_node):

        # Ignore everything except function definitions
        if not isinstance(node, ast.FunctionDef):
            continue

        # Ignore the function we're currently analyzing
        if node is function_node:
            continue

        # Any other FunctionDef is nested
        issues.append(
            {
                "severity": "WARNING",
                "message": "Nested function definition detected.",
            }
        )

    return issues