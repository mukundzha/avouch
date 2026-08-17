import ast

from avouch.utility.walk import walk

def analyze(function_node, limits):
    issues = []

    max_lambda_nodes = limits.get("max_lambda_nodes", 5)

    for node in walk(function_node):
        if isinstance(node,ast.Lambda):
         body_size = len(list(walk(node.body)))
         if body_size > max_lambda_nodes:
            issues.append(
                {
                    "rule": "SCR008",
                    "severity": "WARNING",
                    "message": (
                        f"Lambda function too complex "
                        f"({body_size}/{max_lambda_nodes}). "
                        f"Convert to a named function for clarity."
                    ),
                }
             )

    return issues