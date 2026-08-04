import sys

_USE_COLOR = sys.stdout.isatty()


def generate_report(function_reports, file_reports, class_reports):
    render_report(function_reports, file_reports, class_reports)


def render_report(function_reports, file_reports, class_reports):

    # Combine every report into one list
    all_reports = [
        *class_reports,
        *function_reports,
        *file_reports,
    ]

    # Store issues grouped by file
    issues_by_file = {}

    # Process every report
    for report in all_reports:

        # Ignore reports that have no issues
        if not report["issues"]:
            continue

        # Function or class report
        if "file" in report:

            file_name = report["file"]

            if "parameters" in report:
                item_name = report["name"] + "()"
            else:
                item_name = report["name"]

        # File report
        else:
            file_name = report["name"]
            item_name = "file"

        # Create file bucket if it doesn't exist
        if file_name not in issues_by_file:
            issues_by_file[file_name] = []

        # Store every issue
        for issue in report["issues"]:

            issues_by_file[file_name].append(
                (
                    item_name,
                    issue["message"],
                    issue["severity"],
                    issue.get("rule"),
                )
            )

    # Nothing to show
    if not issues_by_file:
        print(_style("✓ All clean.", 32))
        return

    total_files = len(file_reports)
    failed_files = len(issues_by_file)
    passed_files = total_files - failed_files

    render_summary(failed_files, passed_files)

    # Print every file
    for file_name in sorted(issues_by_file):
        render_file(file_name, issues_by_file[file_name])

    if passed_files:
        print(_style(f"✓ {passed_files} compliant files hidden", 32))


print("")
def render_summary(failed_files, passed_files):

    if passed_files:
        summary = (
            _style(str(failed_files), 33)
            + " file(s) need attention · "
            + _style(str(passed_files), 32)
            + " file(s) passed"
        )
    else:
        summary = _style(str(failed_files), 33) + " file(s) need attention"

    print(
        _style("SCRUT", 1)
        + _style(" [Review Summary]", 2)
        + _style(" — ", 2)
        + summary
    )
    print()


def render_file(file_name, issues):

    print(_style(file_name, 1, 36))

    for item_name, message, severity, rule in issues:

        if severity == "ERROR":
            icon = "✖"
            color = 31
        else:
            icon = "⚠"
            color = 33

        rule_label = _style(rule, 36) if rule else ""

        print(
            f"  {_style(icon, color)} "
            f"{_style(item_name, 1)} "
            + (f"{rule_label} " if rule else "")
            + f"{_style('—', 2)} "
            f"{_style(message, color)}"
        )


def _style(text, *codes):

    if not _USE_COLOR:
        return text

    ansi = ";".join(str(code) for code in codes)

    return f"\033[{ansi}m{text}\033[0m"