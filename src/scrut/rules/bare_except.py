import ast

from scrut.utility.walk import walk


def analyze(function_node, limits):

    issues = []

    for node in walk(function_node):

        if not isinstance(node, ast.ExceptHandler):
            continue

        # Check if the handler is a bare except
        if node.type is None:
         issues.append(
             {
                 "rule": "SCR002",
                 "severity": "WARNING",
                "message": "Bare except detected. Catch a specific exception instead, e.g. except ValueError:.",
            }
        )

    return issues