import ast

from avouch.utility.walk import walk


def analyze(function_node, limits):

    issues = []

    variables = set()

    max_variables = limits.get("max_local_variables", 15)

    for node in walk(function_node):

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
                "rule": "SCR009",
                "severity": "WARNING",
                "message": (
                    f"Too many local variables "
                    f"({total_variables}/{max_variables}). "
                    f"Extract logic into helper functions or use data classes."
                ),
            }
        )

    return issues