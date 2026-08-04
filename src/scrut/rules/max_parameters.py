import ast


def analyze(function_node, limits):

    issues = []

    param_count = len(function_node.args.args)

    if param_count > limits["max_parameters"]:
        issues.append(
            {
                "severity": "WARNING",
                "message": (
                    f"Too many parameters ({param_count}/{limits['max_parameters']}). "
                    f"Group related parameters into a data class or dictionary."
                ),
            }
        )

    return issues
