import ast


def analyze(source_code, limits):

    issues = []

    file_line_count = len(source_code.splitlines())

    if file_line_count > limits["max_file_lines"]:
        issues.append(
            {
                "severity": "WARNING",
                "message": (
                    f"File too large ({file_line_count}/{limits['max_file_lines']}). "
                    f"Split into modules or move unrelated code to separate files."
                ),
            }
        )

    return issues
