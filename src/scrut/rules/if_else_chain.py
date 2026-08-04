import ast


def analyze(function_node, limits):

    issues = []

    max_chain = limits.get("max_if_chain", 5)

    for node in ast.walk(function_node):

        # Only start from an if statement
        if not isinstance(node, ast.If):
            continue

        chain_length = 1
        current = node

        # Follow every elif
        while (
            len(current.orelse) == 1
            and isinstance(current.orelse[0], ast.If)
        ):
            chain_length += 1
            current = current.orelse[0]

        if chain_length > max_chain:
            issues.append(
                {
                    "rule": "SCR007",
                    "severity": "WARNING",
                    "message": (
                        f"Long if/elif chain "
                        f"({chain_length}/{max_chain}). "
                        f"Refactor into a dictionary dispatch or match statement."
                    ),
                }
            )

    return issues