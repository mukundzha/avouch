import ast


def analyze(function_node, limits):

    issues = []

    for node in ast.walk(function_node):

        # Skip everything that is not an except block
        if not isinstance(node, ast.ExceptHandler):
            continue

        # Check if the except block only contains "pass"
        if (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
        ):
            issues.append(
                {
                    "severity": "WARNING",
                    "message": "Empty except block. Handle the exception instead of ignoring it.",
                }
            )

    return issues