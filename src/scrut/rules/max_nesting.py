import ast

BLOCK_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)


def get_depth(node, depth=0):
    max_depth = depth

    for child in ast.iter_child_nodes(node):

        if isinstance(child, BLOCK_NODES):
            max_depth = max(max_depth, get_depth(child, depth + 1))
        else:
            max_depth = max(max_depth, get_depth(child, depth))

    return max_depth


def analyze(function_node, limits):

    issues = []

    nesting_depth = get_depth(function_node)

    if nesting_depth > limits["max_nesting"]:
        issues.append(
            {
                "severity": "WARNING",
                "message": (
                    f"Nesting too deep ({nesting_depth}/{limits['max_nesting']}). "
                    f"Flatten control flow with early returns or guard clauses."
                ),
            }
        )

    return issues
