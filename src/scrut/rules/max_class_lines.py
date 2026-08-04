import ast


def analyze(class_node, limits):

    issues = []

    line_count = class_node.end_lineno - class_node.lineno + 1

    if line_count > limits["max_class_lines"]:
        issues.append(
            {
                "rule": "SCR010",
                "severity": "WARNING",
                "message": (
                    f"Class too large ({line_count}/{limits['max_class_lines']}). "
                    f"Split into smaller classes with single responsibilities."
                ),
            }
        )

    return issues
