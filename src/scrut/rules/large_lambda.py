import ast

def analyze(function_node, limits):
    issues = []

    max_lambda_nodes = limits.get("max_lambda_nodes", 5)

    for node in ast.walk(function_node):
        if isinstance(node,ast.Lambda):
         body_size = len(list(ast.walk(node.body)))
         if body_size > max_lambda_nodes:
            issues.append(
                {
                    "severity": "WARNING",
                    "message": (
                        f"Lambda function too complex "
                        f"({body_size}/{max_lambda_nodes}). "
                        f"Convert to a named function for clarity."
                    ),
                }
             )

    return issues