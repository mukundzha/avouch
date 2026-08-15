import ast
import os
import re
import shutil
import sys
import unicodedata
import json
from pathlib import Path

from scrut.git import get_file_diff

_USE_COLOR = sys.stdout.isatty()

_RED = 31
_GREEN = 32
_BLUE = 34
_CYAN = 36
_BOLD = 1
_DIM = 2

# How many lines the passing grid may occupy before collapsing
_MAX_PASSING_LINES = 4

_TERMINAL_WIDTH = shutil.get_terminal_size((80, 24)).columns

# Editorial layout: dividers never exceed this, columns clamp to it
_LINE_WIDTH = min(_TERMINAL_WIDTH, 80)

_INDENT = "  "

# Messages carry the measured/limit pair, e.g. "Too many parameters (6/5). ..."
_COUNT = re.compile(r"\((\d+/\d+)\)")

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

# Unchanged lines kept around each changed region
_CTX = 1

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


def vlog(verbose, message):

    if verbose:
        print(f"scrut: {message}", file=sys.stderr)


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
                    "line": report.get("line"),
                }
            )

    summary = {
        "total": len(violations),
        "errors": sum(1 for v in violations if v["severity"] == "ERROR"),
        "warnings": sum(1 for v in violations if v["severity"] != "ERROR"),
        "files_with_violations": len({v["file"] for v in violations}),
    }

    print(
        json.dumps(
            {"version": 1, "tool": "scrut", "violations": violations, "summary": summary},
            indent=2,
        )
    )


def render_diff_view(file_paths):

    _set_font()
    print(_style("[CHANGED FILES]", _BOLD))
    print()

    for index, file_path in enumerate(file_paths):

        if index:
            print()

        added, deleted, hunks, labels, is_new = _diff_view(file_path)

        marker = "✓ " if is_new else ""

        print(
            _INDENT
            + (_style(marker, _GREEN) if marker else "")
            + _style(file_path, _BOLD, _CYAN)
            + "  "
            + _style(f"+{added}", _GREEN)
            + " "
            + _style(f"-{deleted}", _RED)
        )
        print(_style(_INDENT + "─" * max(_LINE_WIDTH - 2, 12), _DIM))

        for hunk in hunks:
            _render_hunk(hunk, labels)


def _diff_view(file_path):

    text = get_file_diff(file_path)

    if text is None:
        try:
            lines = Path(file_path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            lines = []
        hunks = [[("add", number, line) for number, line in enumerate(lines, 1)]]
        return len(lines), 0, hunks, _context_labels(file_path), True

    added, deleted, hunks = _parse_diff(text)

    return added, deleted, hunks, _context_labels(file_path), False


def _parse_diff(text):

    added = 0
    deleted = 0
    hunks = []
    hunk = None
    new_pos = 0

    for line in text.splitlines():

        if line.startswith("@@"):
            match = _HUNK.match(line)
            if not match:
                continue
            new_pos = int(match.group(1))
            hunk = []
            hunks.append(hunk)
            continue

        if hunk is None or line.startswith("\\"):
            continue

        tag = line[0]

        if tag == "+":
            added += 1
            hunk.append(("add", new_pos, line[1:]))
            new_pos += 1
        elif tag == "-":
            deleted += 1
            hunk.append(("del", None, line[1:]))
        elif tag == " ":
            hunk.append(("ctx", new_pos, line[1:]))
            new_pos += 1

    return added, deleted, [_trim_hunk(hunk) for hunk in hunks]


def _trim_hunk(hunk):

    first = None
    last = None

    for index, (tag, _, _) in enumerate(hunk):

        if tag != "ctx":
            if first is None:
                first = index
            last = index

    if first is None:
        return []

    return hunk[max(0, first - _CTX) : last + 1 + _CTX]


def _render_hunk(hunk, labels):

    current_label = None

    for tag, line_number, text in hunk:

        if tag != "del":
            label = labels.get(line_number)

            if label and label != current_label:
                print(_style(_INDENT + _INDENT + "  " + label, _DIM))
                current_label = label

        if tag == "add":
            print(_style(_INDENT + _INDENT + "+ " + text, _GREEN))
        elif tag == "del":
            print(_style(_INDENT + _INDENT + "- " + text, _RED))
        else:
            print(_INDENT + _INDENT + "  " + text)


def _context_labels(file_path):

    try:
        tree = ast.parse(Path(file_path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return {}

    labels = {}

    for node in ast.walk(tree):

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                label = f"def {node.name}"
            else:
                label = f"class {node.name}"

            for line in range(node.lineno, node.end_lineno + 1):
                labels[line] = label

    return labels


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
                    report.get("line"),
                )
            )

            if severity == "ERROR":
                error_count += 1
            else:
                warning_count += 1

    total_files = len(file_reports)

    # Nothing to show
    if not issues_by_file:
        print(_style("All clean.", _BOLD))
        return

    print(
        _style("SCRUT", _BOLD)
        + f" · {_count_segment(total_files, 'FILE', 'FILES')}"
        + _count_parts(error_count, warning_count)
    )
    print(_style("─" * _LINE_WIDTH, _DIM))
    print()

    first = True
    rule_counts = {}
    rule_labels = {}

    for file_name in sorted(issues_by_file):

        try:
            source_lines = Path(file_name).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            source_lines = []

        for item_name, rule_id, rule_name, metric, is_error, line, message in _issue_rows(
            issues_by_file[file_name]
        ):

            if not first:
                print()

            first = False

            _render_finding(
                (file_name, item_name, rule_id, rule_name, message, is_error, line),
                source_lines,
            )

            key = rule_id or rule_name
            rule_counts[key] = rule_counts.get(key, 0) + 1
            rule_labels[key] = rule_name

    if rule_counts:
        print()
        _render_rule_summary(rule_counts, rule_labels)

    passing_files = [
        report["name"]
        for report in file_reports
        if report["name"] not in issues_by_file
    ]

    if passing_files:
        print()
        print(_style("─" * _LINE_WIDTH, _DIM))
        print(_style("PASSED", _BOLD))
        render_passing(passing_files)


def _render_finding(finding, source_lines):

    file_name, item_name, rule_id, rule_name, message, is_error, line = finding

    display_line = line or 1

    location = _style(file_name, _BOLD, _CYAN) + _style(f":{display_line}:", _DIM)

    message_part = _style(message, _RED) if is_error else message

    if rule_id:
        header = (
            location + " " + _style(rule_id, _BLUE) + ": " + message_part
        )
    else:
        header = location + " " + message_part

    print(header)

    if display_line > len(source_lines):
        return

    head = max(display_line - _CTX, 1)
    tail = min(display_line + _CTX, len(source_lines))
    width = len(str(tail))

    caret = None

    if item_name != "file":
        col = source_lines[display_line - 1].find(item_name)

        if col != -1:
            caret = (
                " " * col
                + "^" * len(item_name)
                + " "
                + _style(rule_id or rule_name, _BLUE)
            )

    print(" " * width + " │")

    for number in range(head, tail + 1):

        print(
            f"{number:>{width}} │ " + _style(source_lines[number - 1], _DIM)
        )

        if number == display_line and caret is not None:
            print(" " * width + " │ " + caret)

    print(" " * width + " │")


def _render_rule_summary(rule_counts, rule_labels):

    ordered = sorted(rule_counts, key=lambda key: (-rule_counts[key], key))

    plain = []

    for key in ordered:

        label = rule_labels[key]

        if label == key:
            plain.append(label)
        else:
            plain.append(key + " " + label)

    rule_width = max(_display_width(cell) for cell in plain)
    count_width = max(len(str(rule_counts[key])) for key in ordered)

    print(_style("─" * _LINE_WIDTH, _DIM))
    print(_style("BY RULE", _BOLD))
    print()

    for cell, key in zip(plain, ordered):

        if cell == rule_labels[key]:
            styled = cell
        else:
            styled = _style(key, _BLUE) + " " + rule_labels[key]

        print(
            _INDENT
            + styled
            + " " * (2 + rule_width - _display_width(cell))
            + _style(str(rule_counts[key]).rjust(count_width), _BOLD)
        )


def render_passing(passing_files):

    total = len(passing_files)

    if not total:
        return

    name_width = max(_display_width(name) for name in passing_files)

    columns = max(1, (min(_TERMINAL_WIDTH, 120) - 4) // (name_width + 4))

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
            _INDENT
            + "  ".join(
                styled + " " * (cell_width - _display_width(plain))
                for styled, plain in cells[start : start + columns]
            ).rstrip()
        )


def _issue_rows(entries):

    rows = []
    file_rows = []
    seen = set()
    file_seen = set()

    for item_name, kind, message, severity, rule_id, line in entries:

        rule_name = _rule_label(message)
        metric = _count_value(message)

        # The metric column renders "detected"; don't repeat it in the rule
        if not metric and rule_name.endswith(" detected"):
            rule_name = rule_name[: -len(" detected")]

        if item_name == "file":
            key = (rule_name, metric)
            if key in file_seen:
                continue
            file_seen.add(key)
            file_rows.append(
                (item_name, rule_id, rule_name, metric, severity == "ERROR", line, message)
            )
            continue

        key = (item_name, rule_name, metric)

        if key in seen:
            continue

        seen.add(key)
        rows.append(
            (item_name, rule_id, rule_name, metric, severity == "ERROR", line, message)
        )

    combined = file_rows + rows

    # File-level rows first, then by line, then by rule id
    return sorted(combined, key=_issue_order)


def _issue_order(row):

    return row[5] or 0, row[1] or ""


def _count_segment(count, singular, plural):

    return _style(str(count), _BOLD) + " " + (singular if count == 1 else plural)


def _count_parts(error_count, warning_count):

    parts = []

    if warning_count:
        parts.append(_style(str(warning_count), _BOLD) + " WARN")
    if error_count:
        parts.append(_style(str(error_count), _BOLD) + " ERR")

    if not parts:
        return ""

    return " · " + " · ".join(parts)


def _rule_label(message):

    # First sentence of the message, without the measured/limit pair
    first = message.split(".", 1)[0]
    first = _COUNT.sub("", first).strip()

    return first or message


def _count_value(message):

    match = _COUNT.search(message)

    return match.group(1) if match else ""


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