import sys

_USE_COLOR = sys.stdout.isatty()


def render_report(function_reports, file_reports, class_reports):

    issues = {}

    for report in [*class_reports, *function_reports, *file_reports]:

        file = report.get("file", report["name"])

        if not report["issues"]:
            continue

        if "file" in report:
            name = report["name"] + ("()" if "parameters" in report else "")
        else:
            name = "file"

        for issue in report["issues"]:
            issues.setdefault(file, []).append(
                (name, issue["message"], issue["severity"])
            )

    if not issues:
        print(_style("✓ All clean.", 32))
        return

    passed = len(file_reports) - len(issues)

    print("")
    print(_style("SCRUT", 1) + _style(" [Review Summary] ", 2))
    print()
    print(
        _style(str(len(issues)), 33)
        + _style(" file(s) need attention · ", 0)
        + _style(str(passed), 32)
        + _style(" file(s) passed", 0)
    )
    print()

    for file, items in sorted(issues.items()):

        print(_style(file, 1, 36))

        for name, message, severity in items:
            icon, color = ("✖", 31) if severity == "ERROR" else ("⚠", 33)
            print(
                f"  {_style(icon, color)} "
                f"{_style(name, 1)} {_style('—', 2)} {_style(message, color)}"
            )

    print()

    if passed:
        print(_style(f"✓ {passed} compliant files hidden", 32))


def _style(text, *codes):

    if not _USE_COLOR:
        return text

    return f"\033[{';'.join(str(code) for code in codes)}m{text}\033[0m"


def generate_report(function_reports, file_reports, class_reports):
    render_report(function_reports, file_reports, class_reports)
