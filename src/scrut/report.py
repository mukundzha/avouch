import sys

_USE_COLOR = sys.stdout.isatty()


def generate_report(function_reports, file_reports, class_reports):
    render_report(function_reports, file_reports, class_reports)


def render_report(function_reports, file_reports, class_reports):

    reports = []
    reports.extend(class_reports)
    reports.extend(function_reports)
    reports.extend(file_reports)
    issues_by_file = {}


    for report in reports:

        if len(report["issues"]) == 0:
            continue

        if "file" in report:
            file_name = report["file"]

            if "parameters" in report:
                item_name = report["name"] + "()"
            else:
                item_name = report["name"]

        else:
            file_name = report["name"]
            item_name = "file"

        if file_name not in issues_by_file:
            issues_by_file[file_name] = []

        for issue in report["issues"]:

            issues_by_file[file_name].append(
                (
                    item_name,
                    issue["message"],
                    issue["severity"],
                )
            )

    if len(issues_by_file) == 0:
        print(_style("✓ All clean.", 32))
        return

    total_files = len(file_reports)
    files_with_issues = len(issues_by_file)
    passed_files = total_files - files_with_issues


    render_summary(files_with_issues, passed_files)

    for file_name in sorted(issues_by_file):

        render_file(file_name, issues_by_file[file_name])

    print()

    if passed_files > 0:
        print(_style(f"✓ {passed_files} compliant files hidden", 32))


def render_summary(files_with_issues, passed_files):

    print()
    print(_style("SCRUT", 1) + _style(" [Review Summary]", 2))
    print()

    if passed_files > 0:
     print(
        _style(str(files_with_issues), 33)
        + " file(s) need attention · "
        + _style(str(passed_files), 32)
        + " file(s) passed"
    )
    else:
     print(
        _style(str(files_with_issues), 33)
        + " file(s) need attention"
    )
    print()


def render_file(file_name, issues):

    print(_style(file_name, 1, 36))

    for item_name, message, severity in issues:

        if severity == "ERROR":
            icon = "✖"
            color = 31
        else:
            icon = "⚠"
            color = 33

        print(
            f"  {_style(icon, color)} "
            f"{_style(item_name, 1)} "
            f"{_style('—', 2)} "
            f"{_style(message, color)}"
        )

    print()


def _style(text, *codes):

    if not _USE_COLOR:
        return text

    code = ";".join(str(value) for value in codes)
    return f"\033[{code}m{text}\033[0m"