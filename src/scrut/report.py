import os
import re
import shutil
import sys
import unicodedata
import json

_USE_COLOR = sys.stdout.isatty()

_RED = 31
_GREEN = 32
_BLUE = 34
_CYAN = 36
_BOLD = 1
_DIM = 2

_ICON_ERROR = "🔴"
_ICON_WARNING = "🟡"
_ICON_PASS = "🟢"
_ICON_FUNC = "📊"
_ICON_BAD_FILE = "🛑"
_ICON_WARN_FILE = "⚠️"

# How many lines the passing grid may occupy before collapsing
_MAX_PASSING_LINES = 4

_TERMINAL_WIDTH = shutil.get_terminal_size((80, 24)).columns

# Messages carry the measured/limit pair, e.g. "Too many parameters (6/5). ..."
_COUNT = re.compile(r"\((\d+/\d+)\)")

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

_RAIL = "│  "

_FONT_APPLIED = False


def _set_font():

    global _FONT_APPLIED

    font = os.environ.get("SCRUT_FONT")

    # Opt-in terminal font override (OSC 50, ignored by unsupported terminals)
    if _FONT_APPLIED or not (_USE_COLOR and font):
        return

    _FONT_APPLIED = True
    print(f"\x1b]50;SetFont={font}\x07", end="")


def generate_report(function_reports, file_reports, class_reports):
    render_report(function_reports, file_reports, class_reports)


def render_json(function_reports, file_reports, class_reports):

    violations = []

    for report in class_reports + function_reports + file_reports:

        if "file" in report:
            file_name = report["file"]
            item_name = report["name"]

            if "parameters" in report:
                kind = "func"
            else:
                kind = "class"

        else:
            file_name = report["name"]
            item_name = "file"
            kind = "file"

        for issue in report["issues"]:
            violations.append(
                {
                    "rule": issue.get("rule") or _rule_label(issue["message"]),
                    "severity": issue["severity"],
                    "message": issue["message"],
                    "file": file_name,
                    "name": item_name,
                    "kind": kind,
                }
            )

    summary = {
        "total": len(violations),
        "errors": sum(1 for v in violations if v["severity"] == "ERROR"),
        "warnings": sum(1 for v in violations if v["severity"] != "ERROR"),
        "files_with_violations": len({v["file"] for v in violations}),
    }

    print(json.dumps({"version": 1, "violations": violations, "summary": summary}, indent=2))


def render_report(function_reports, file_reports, class_reports):

    _set_font()
    print()

    issues_by_file = {}
    error_count = 0
    warning_count = 0

    # Combine every report into one list
    all_reports = [
        *class_reports,
        *function_reports,
        *file_reports,
    ]

    # Group issues by file in a single pass
    for report in all_reports:

        # Ignore reports that have no issues
        if not report["issues"]:
            continue

        # Function or class report
        if "file" in report:
            file_name = report["file"]
            item_name = report["name"]

            if "parameters" in report:
                kind = "func"
            else:
                kind = "class"

        # File report
        else:
            file_name = report["name"]
            item_name = "file"
            kind = "file"

        bucket = issues_by_file.setdefault(file_name, [])

        # Store every issue
        for issue in report["issues"]:

            severity = issue["severity"]

            bucket.append(
                (
                    item_name,
                    kind,
                    issue["message"],
                    severity,
                    issue.get("rule"),
                )
            )

            if severity == "ERROR":
                error_count += 1
            else:
                warning_count += 1

    # Nothing to show
    if not issues_by_file:
        print(_style("scrut", _BOLD) + " " + _style("[Review Summary]", _DIM))
        print(_box([_ICON_PASS + " All clean."]))
        return

    total_files = len(file_reports)
    failed_files = len(issues_by_file)
    passed_files = total_files - failed_files

    render_summary(error_count, warning_count, passed_files, len(function_reports))

    _section("[NEEDS REVIEW]")

    # Print every file that needs attention
    for index, file_name in enumerate(sorted(issues_by_file)):

        render_file(file_name, issues_by_file[file_name])

        if index < failed_files - 1:
            print()

    # Collapsed list of compliant files
    if passed_files:
        passing_files = [
            report["name"]
            for report in file_reports
            if report["name"] not in issues_by_file
        ]
        render_passing(passing_files)


def render_summary(error_count, warning_count, passed_files, function_count):

    segments = []

    if error_count:
        segments.append(_segment(_ICON_ERROR, error_count, "error", "errors"))
    if warning_count:
        segments.append(_segment(_ICON_WARNING, warning_count, "warning", "warnings"))
    if passed_files:
        segments.append(_segment(_ICON_PASS, passed_files, "passed", "passed"))
    if function_count:
        segments.append(_segment(_ICON_FUNC, function_count, "func checked", "funcs checked"))

    print(_style("scrut", _BOLD) + " " + _style("[Review Summary]", _DIM))
    print(_box(segments))
    print()


def render_file(file_name, entries):

    rows = _issue_rows(entries)

    has_error = any(row[4] for row in rows)

    if has_error:
        icon = _ICON_BAD_FILE
    else:
        icon = _ICON_WARN_FILE

    print(
        _style("╭─ ", _DIM)
        + icon
        + " "
        + _style(file_name, _BOLD, _CYAN)
        + _style(f" ({len(entries)})", _DIM)
    )

    if rows:
        _print_table(rows)


def render_passing(passing_files):

    print()
    _section("[PASSING]")

    total = len(passing_files)

    if not total:
        return

    name_width = max(_display_width(name) for name in passing_files)

    columns = max(1, (min(_TERMINAL_WIDTH, 120) - 2) // (name_width + 4))

    capacity = _MAX_PASSING_LINES * columns

    if total <= capacity:
        shown = passing_files
        hidden = 0
    else:
        shown = passing_files[: capacity - 1]
        hidden = total - (capacity - 1)

    cells = [(_style("✓ " + name, _GREEN), "✓ " + name) for name in shown]

    if hidden:
        cells.append((_style(f"[+{hidden} more]", _DIM), f"[+{hidden} more]"))

    cell_width = max(_display_width(plain) for _, plain in cells)

    for start in range(0, len(cells), columns):
        print(
            "  ".join(
                styled + " " * (cell_width - _display_width(plain))
                for styled, plain in cells[start : start + columns]
            ).rstrip()
        )


def _issue_rows(entries):

    rows = []
    file_rows = []
    seen = set()
    file_seen = set()

    for item_name, kind, message, severity, _ in entries:

        rule = _rule_label(message)
        metric = _count_value(message)

        # The metric column renders "detected"; don't repeat it in the rule
        if not metric and rule.endswith(" detected"):
            rule = rule[: -len(" detected")]

        if item_name == "file":
            key = (rule, metric)
            if key in file_seen:
                continue
            file_seen.add(key)
            file_rows.append(
                ("<file>", "file", rule, metric, severity == "ERROR")
            )
            continue

        key = (item_name, rule, metric)

        if key in seen:
            continue

        seen.add(key)
        rows.append((item_name, kind, rule, metric, severity == "ERROR"))

    return file_rows + rows


def _print_table(rows):

    use_metric = any(row[3] for row in rows)

    if use_metric:
        headers = ("Component", "Kind", "Rule", "Metric")
    else:
        headers = ("Component", "Kind", "Rule")

    widths = [_display_width(header) for header in headers]

    for component, kind, rule, metric, _ in rows:
        widths[0] = max(widths[0], _display_width(component))
        widths[1] = max(widths[1], _display_width(kind))
        widths[2] = max(widths[2], _display_width(rule))
        if use_metric:
            widths[3] = max(widths[3], _display_width(metric))

    gaps = len(headers) - 1
    rail = _display_width(_RAIL)
    free = (
        _TERMINAL_WIDTH
        - rail
        - gaps * 2
        - (widths[3] + 2 if use_metric else 0)
    )

    # Clamp the variable columns so the table never exceeds the terminal
    if widths[0] + widths[2] > free:
        component_col = min(widths[0], max(10, int(free * 0.45)))
        widths[0] = component_col
        widths[2] = max(free - component_col, 12)

    header = _style(
        _fit(headers[0], widths[0]).ljust(widths[0])
        + "  "
        + _fit(headers[1], widths[1]).ljust(widths[1])
        + "  "
        + _fit(headers[2], widths[2]).ljust(widths[2])
        + ("  " + headers[3].rjust(widths[3]) if use_metric else ""),
        _BOLD,
    )

    print(_RAIL + header)
    print(_RAIL + "─" * (sum(widths) + gaps * 2))

    for row in rows:
        print(_row_line(row, widths, use_metric))


def _row_line(row, widths, use_metric):

    component, kind, rule, metric, is_error = row

    gap = "  "
    color = _RED if is_error else None

    cells = [
        _pad(_fit(component, widths[0]), widths[0]),
        _pad(_fit(kind, widths[1]), widths[1], _DIM),
        _pad(_fit(rule, widths[2]), widths[2], color),
    ]

    if use_metric and metric:
        cells.append(_style(metric.rjust(widths[3]), _BLUE))
    elif use_metric:
        cells.append(_style("detected".rjust(widths[3]), _BLUE))

    return (_RAIL + gap.join(cells)).rstrip()


def _pad(text, width, code=None):

    padded = text.ljust(width)

    if code:
        return _style(padded, code)

    return padded


def _fit(text, width):

    if _display_width(text) <= width:
        return text

    head = text

    while head and _display_width(head) >= width:
        head = head[:-1]

    if head:
        return head + "…"

    return "…"


def _rule_label(message):

    # First sentence of the message, without the measured/limit pair
    first = message.split(".", 1)[0]
    first = _COUNT.sub("", first).strip()

    return first or message


def _count_value(message):

    match = _COUNT.search(message)

    return match.group(1) if match else ""


def _section(title):

    filler = "─" * max(min(_TERMINAL_WIDTH - len(title) - 2, 60), 12)
    print(_style(title, _BOLD) + " " + _style(filler, _DIM))
    print()


def _segment(icon, count, singular, plural):

    label = singular if count == 1 else plural

    return f"{icon} {_style(str(count), _BOLD)} {label}"


def _box(segments):

    if not segments:
        return ""

    plain = [_ANSI.sub("", segment) for segment in segments]
    width = max(_display_width(text) for text in plain)
    separator = _style(" │ ", _DIM)

    # Fit within the terminal: pad uniformly when there is room,
    # otherwise fall back to natural widths so the box never wraps
    padded_width = sum(width for _ in segments) + 3 * (len(segments) - 1) + 2

    if padded_width > max(24, _TERMINAL_WIDTH - 2):
        body = separator.join(segments)
    else:
        body = separator.join(
            segment + " " * (width - _display_width(text))
            for segment, text in zip(segments, plain)
        )

    inner = " " + body + " "
    bar = "═" * _display_width(_ANSI.sub("", inner))

    return "\n".join(
        (
            _style("╔" + bar + "╗", _DIM),
            _style("║", _DIM) + inner + _style("║", _DIM),
            _style("╚" + bar + "╝", _DIM),
        )
    )


def _display_width(text):

    width = 0

    for char in text:

        if char in "\u200d\ufe0f":
            continue

        if (
            ord(char) > 0x1F000
            or char == "⚠"
            or unicodedata.east_asian_width(char) in ("W", "F")
        ):
            width += 2
        else:
            width += 1

    return width


def _style(text, *codes):

    if not _USE_COLOR:
        return text

    ansi = ";".join(str(code) for code in codes)

    return f"\033[{ansi}m{text}\033[0m"