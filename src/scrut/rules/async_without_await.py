import ast

from scrut.utility.walk import walk


def analyze(function_node, limits):

    issues = []

    if any(isinstance(node, ast.Await) for node in walk(function_node)):
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