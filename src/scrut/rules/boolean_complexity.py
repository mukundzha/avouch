import ast

def count_boolean_conditions(node):
    if isinstance(node, ast.BoolOp):
        return sum(count_boolean_conditions(value) for value in node.values)

    return 1


def analyze(function_node, limits):

    issues = []

    for node in ast.walk(function_node):

        if isinstance(node, ast.BoolOp):

            condition_count = count_boolean_conditions(node)

            if condition_count > limits["max_boolean_conditions"]:

                issues.append(
                    {
                        "severity": "WARNING",
                        "message": (
                            f"Boolean expression too complex "
                            f"({condition_count}/{limits['max_boolean_conditions']})"
                        ),
                    }
                )

    return issues

