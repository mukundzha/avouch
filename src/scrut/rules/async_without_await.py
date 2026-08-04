import ast


def analyze(function_node, limits):

    issues = []

    if any(isinstance(node, ast.Await) for node in ast.walk(function_node)):
        return issues

    issues.append(
        {
            "rule": "SCR001",
            "severity": "WARNING",
            "message": (
                "Async function contains no await expression. "
                "Consider using a regular function."
            ),
        }
    )

    return issues