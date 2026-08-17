import ast

from scrut.utility.walk import walk


def analyze(function_node, limits):

    issues = []

    for node in walk(function_node):

        # Skip everything that is not an if statement
        if not isinstance(node, ast.If):
            continue

        branches = []

        # Add the main if branch
        branches.append(node.body)

        # Add elif branches
        current = node.orelse

        while (
            len(current) == 1
            and isinstance(current[0], ast.If)
        ):
            branches.append(current[0].body)
            current = current[0].orelse

        seen = set()

        for branch in branches:

            # Convert branch AST into comparable form
            branch_code = ast.dump(
                ast.Module(
                    body=branch,
                    type_ignores=[]
                )
            )

            if branch_code in seen:
                issues.append(
                    {
                        "rule": "SCR004",
                        "severity": "WARNING",
                        "message": "Duplicate branch detected. Multiple if/elif branches contain the same logic. Merge duplicate branches or verify the condition is correct.",
                    }
                )
                break

            seen.add(branch_code)

    return issues