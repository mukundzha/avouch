import ast


def _collect_chain(if_node):
    """Fold an if/elif/else chain into its branch bodies and if nodes."""

    branches = [if_node.body]
    chain_nodes = [if_node]
    current = if_node.orelse

    while len(current) == 1 and isinstance(current[0], ast.If):
        chain_nodes.append(current[0])
        branches.append(current[0].body)
        current = current[0].orelse

    if len(current) > 0:
        branches.append(current)

    return branches, chain_nodes


def analyze(function_node, limits):

    issues = []
    consumed = set()

    for node in ast.walk(function_node):

        if not isinstance(node, ast.If):
            continue

        if id(node) in consumed:
            continue

        branches, chain_nodes = _collect_chain(node)
        consumed.update(id(item) for item in chain_nodes)

        if len(branches) > limits["max_if_else_chain"]:
            issues.append(
                {
                    "severity": "WARNING",
                    "message": (
                        f"If-else chain too long "
                        f"({len(branches)}/{limits['max_if_else_chain']})"
                    ),
                }
            )

    return issues