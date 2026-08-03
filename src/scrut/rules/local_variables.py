import ast


def analyze(function_node, limits):

    issues = []

    variables = set()

    max_variables = limits.get("max_local_variables", 15)

    for node in ast.walk(function_node):

        # Is this an assignment?
        if not isinstance(node, ast.Assign):
            continue

        # Look at every variable on the left side
        for target in node.targets:

            # Is it a normal variable?
            if isinstance(target, ast.Name):
                variables.add(target.id)

    total_variables = len(variables)

    if total_variables > max_variables:

        issues.append(
            {
                "severity": "WARNING",
                "message": (
                    f"Too many local variables "
                    f"({total_variables}/{max_variables})"
                ),
            }
        )

    return issues