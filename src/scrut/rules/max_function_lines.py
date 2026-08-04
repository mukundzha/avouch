import ast


def analyze(function_node, limits):

    issues = []

    line_count = function_node.end_lineno - function_node.lineno + 1

    if line_count > limits["max_function_lines"]:
        issues.append(
            {
                "rule": "SCR012",
                "severity": "WARNING",
                "message": (
                    f"Function too long ({line_count}/{limits['max_function_lines']}). "
                    f"Extract helper functions or split into smaller units."
                ),
            }
        )

    return issues
