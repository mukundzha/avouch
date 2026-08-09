from collections import Counter

from rich.console import Console, Group
from rich.text import Text
from rich.padding import Padding

console = Console()


class RunResult:
    """Structured analysis result consumed by the renderer."""

    def __init__(self, files=None, summary=None, metrics=None, total_files=None):
        self.files = files or []
        self.summary = summary or []
        self.metrics = metrics or Counter()
        self.total_files = total_files or len(self.files)


def generate_report(function_reports, file_reports, class_reports):
    result = build_result(function_reports, file_reports, class_reports)
    render_report(result)


def build_result(function_reports, file_reports, class_reports):
    summary = []
    metrics = Counter()

    by_file = {}
    all_reports = [*class_reports, *function_reports, *file_reports]

    for report in all_reports:
        if not report.get("issues"):
            continue

        file_name = report.get("file") or report["name"]
        by_file.setdefault(file_name, {"file": file_name, "items": []})

        name = report["name"]
        if "parameters" in report:
            name = name + "()"

        for issue in report["issues"]:
            rule = issue.get("rule", "")
            short_msg = shorten(issue["message"])
            summary.append((rule, file_name, short_msg))
            metrics[rule] += 1
            by_file[file_name]["items"].append(
                (name, rule, short_msg, issue["severity"])
            )

    result_files = list(by_file.values())
    return RunResult(
        files=result_files,
        summary=summary,
        metrics=metrics,
        total_files=len(file_reports),
    )


SHORT_MESSAGE_MAP = [
    ("too many parameters", "Too many parameters"),
    ("nested function", "Nested function"),
    ("boolean expression too complex", "Complex boolean expression"),
    ("long if/elif chain", "Long if/elif chain"),
    ("too many return statements", "Too many return statements"),
    ("lambda function too complex", "Lambda function"),
    ("large comprehension", "Large comprehension"),
    ("function too long", "Function too long"),
    ("class too large", "Class too large"),
    ("file too large", "File too large"),
    ("nesting too deep", "Nesting too deep"),
    ("function too complex", "Function too complex"),
    ("class too complex", "Class too complex"),
    ("duplicate branch", "Duplicate branch"),
    ("bare except", "Bare except"),
    ("async function contains no await", "Async function"),
]


def shorten(message):
    """Shorten a verbose message into one readable line."""
    lowered = message.lower()
    for needle, replacement in SHORT_MESSAGE_MAP:
        if needle in lowered:
            return replacement
    return message.split(".")[0]


RULE_MESSAGE = {
    "SCR001": "Async function",
    "SCR002": "Bare except",
    "SCR003": "Complex boolean",
    "SCR004": "Duplicate branch",
    "SCR005": "Large comprehension",
    "SCR006": "Duplicate branch",
    "SCR007": "If/elif chain",
    "SCR008": "Lambda function",
    "SCR009": "Too many local variables",
    "SCR010": "Class too large",
    "SCR011": "File too large",
    "SCR012": "Function too long",
    "SCR013": "Nesting too deep",
    "SCR014": "Too many parameters",
    "SCR015": "Nested function",
    "SCR016": "Too many returns",
}


def message_for_rule(rule):
    return RULE_MESSAGE.get(rule, "")


def render_report(result):
    console.print(render_header(result))
    console.print()

    if not result.files:
        console.print(render_clean())
        return

    for file_entry in result.files:
        console.print(render_file(file_entry))

    files_with_issues = len({item["file"] for item in result.files})
    passed = result.total_files - files_with_issues
    console.print()
    console.print(render_summary(result.metrics, passed))


def render_header(result):
    header = Text()
    header.append(Text("Scrut", style="bold"))
    header.append("\n\n")
    count = len(result.summary)
    files_with_issues = len({item["file"] for item in result.files})
    header.append(
        f"{result.total_files} files  {files_with_issues} with issues  {count} findings"
    )
    return header


def render_clean():
    return Text("✓ All clean.", style="green")


def render_file(file_entry):
    lines = [Text(file_entry["file"], style="bold")]

    # Group consecutive items by function name
    grouped = []
    for name, rule, message, severity in file_entry["items"]:
        if grouped and grouped[-1][0] == name:
            grouped[-1][1].append((rule, message))
        else:
            grouped.append((name, [(rule, message)]))

    for name, findings in grouped:
        lines.append(Text(""))
        if name == "file":
            indent = 2
        else:
            lines.append(Padding(Text(name, style="bold"), (0, 0, 0, 2)))
            indent = 4
        for rule, message in findings:
            prefix = f"{rule}  " if rule else ""
            rule_style = "dim" if rule else ""
            lines.append(
                Padding(Text(f"{prefix}{message}", style=rule_style), (0, 0, 0, indent))
            )

    return Group(*lines)


def render_summary(metrics, passed):
    
    lines = [Text("Summary")]

    sorted_metrics = sorted(metrics.items(), key=lambda item: (-item[1], item[0]))
    for rule, count in sorted_metrics:
        message = message_for_rule(rule)
        line = Text()
        rule_label = rule if rule else "—"
        line.append(Text(rule_label, style="dim"))
        line.append(f"  {message}")
        pad = max(1, 24 - len(rule_label) - len(message))
        line.append(" " * pad)
        line.append(str(count))
        lines.append(line)

    lines.append(Text(""))
    lines.append(Text(f"{passed} files passed"))
    return Group(*lines)
