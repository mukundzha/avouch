import ast

from scrut.utility.walk import walk

def analyze(function_node, limits):
    issues = []
    return_count = 0

    limit = limits.get("max_return_statements", 3)

    for node in walk(function_node):
        if not isinstance(node,ast.Return):
            continue
        else:
            return_count += 1


    if return_count > limit:
        issues.append( 
            {
                "rule": "SCR016",
                "severity": "WARNING",
                "message": (
                    f"Too many return statements "
                    f"({return_count}/{limit}). "
                    f"Consolidate return paths or use early returns with a single exit point."
                ),
            }
        )
    return issues