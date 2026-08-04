import ast


def analyze(function_node, limits):

    issues = []

    limit = limits.get("max_large_comprehensions", 10)

    for node in ast.walk(function_node):

        if not isinstance(
            node,
            (
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ):
            continue

        comprehension_size = len(list(ast.walk(node)))

        if comprehension_size > limit:
            issues.append(
                {
                    "severity": "WARNING",
                    "message": (
                        f"Large comprehension "
                        f"({comprehension_size}/{limit}). "
                        f"Extract into a named function or break into multiple steps."
                    ),
                }
            )

    return issues