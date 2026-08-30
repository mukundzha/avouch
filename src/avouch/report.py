import ast
import os
import re
import shutil
import sys
import unicodedata
import json
from pathlib import Path

from avouch.git import get_file_diff

_USE_COLOR = sys.stdout.isatty()

_RED = 31
_GREEN = 32
_BLUE = 34
_CYAN = 36
_BOLD = 1
_DIM = 2

_ACCENT = "#c48a3f"
_ACCENT_DIM = "#8a7a5a"
_MUTED = "#8a8680"
_SUCCESS = "#7a9e7e"
_ERROR = "#c45c4a"
_SURFACE = "#1a1918"
_BORDER = "#55504a"

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

    font = os.environ.get("AVOUCH_FONT")

    # Opt-in terminal font override (OSC 50, ignored by unsupported terminals)
    if _FONT_APPLIED or not (_USE_COLOR and font):
        return

    _FONT_APPLIED = True
    print(f"\x1b]50;SetFont={font}\x07", end="")


def generate_report(function_reports, file_reports, class_reports, suppressed=0):
    render_report(function_reports, file_reports, class_reports, suppressed)


def vlog(verbose, message):

    if verbose:
        print(f"avouch: {message}", file=sys.stderr)


def _collect_violations(function_reports, file_reports, class_reports):

    violations = []

    for report in class_reports + function_reports + file_reports:

        file_name = report.get("file", report["name"])

        for issue in report["issues"]:
            violations.append(
                {
                    "rule": issue.get("rule") or _rule_label(issue["message"]),
                    "severity": issue["severity"],
                    "message": issue["message"],
                    "file": file_name,
                    "name": report["name"],
                    "kind": report["kind"],
                    "line": report.get("line"),
                }
            )

    return sorted(violations, key=lambda v: (v["file"], v["line"] or 0, v["rule"]))


def render_json(function_reports, file_reports, class_reports):

    violations = _collect_violations(function_reports, file_reports, class_reports)

    summary = {
        "total": len(violations),
        "errors": sum(1 for v in violations if v["severity"] == "ERROR"),
        "warnings": sum(1 for v in violations if v["severity"] != "ERROR"),
        "files_with_violations": len({v["file"] for v in violations}),
    }

    print(
        json.dumps(
            {"version": 1, "tool": "avouch", "violations": violations, "summary": summary},
            indent=2,
        )
    )


def _escape_github(text):

    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _column_for(violation):

    try:
        lines = Path(violation["file"]).read_text(encoding="utf-8").splitlines()
        line = violation.get("line")
        name = violation.get("name") or ""
        kind = violation.get("kind") or ""
        if line and 1 <= line <= len(lines) and name and name != "file":
            text = lines[line - 1]
            col = -1
            if kind == "func":
                for pat, off in ((f"def {name}", 4), (f"async def {name}", 10), (f" {name}(", 1)):
                    idx = text.find(pat)
                    if idx != -1:
                        col = idx + off
                        break
            elif kind == "class":
                pat = f"class {name}"
                idx = text.find(pat)
                if idx != -1:
                    col = idx + 6
            if col == -1:
                col = text.find(name)
            if col != -1:
                return col + 1
    except Exception:
        pass
    return 1


def render_github(function_reports, file_reports, class_reports):

    violations = _collect_violations(function_reports, file_reports, class_reports)

    for v in violations:
        kind = "error" if v["severity"] == "ERROR" else "warning"
        col = _column_for(v)
        title = _escape_github(v["rule"])
        msg = _escape_github(v["message"])
        file = v["file"]
        line = v["line"] or 1
        print(f"::{kind} file={file},line={line},col={col},title={title}::{msg}")


def render_sarif(function_reports, file_reports, class_reports):

    import importlib.metadata

    try:
        version = importlib.metadata.version("avouch")
    except Exception:
        version = "0.3.3"

    violations = _collect_violations(function_reports, file_reports, class_reports)

    try:
        from avouch.utility.docs import RULES
    except Exception:
        RULES = {}

    rules = []

    for rid in sorted(RULES):
        spec = RULES[rid]
        rules.append(
            {
                "id": rid,
                "name": spec.get("name", rid),
                "shortDescription": {"text": spec.get("description", "")},
                "helpUri": f"https://github.com/mukundzha/avouch#rule-{rid.lower()}",
            }
        )

    results = []

    for v in violations:
        col = _column_for(v)
        end_col = col + len(v.get("name") or "") if v.get("name") and v["name"] != "file" else col
        level = "error" if v["severity"] == "ERROR" else "warning"
        results.append(
            {
                "ruleId": v["rule"],
                "level": level,
                "message": {"text": v["message"]},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": v["file"]},
                            "region": {
                                "startLine": v["line"] or 1,
                                "startColumn": col,
                                "endLine": v["line"] or 1,
                                "endColumn": end_col,
                            },
                        }
                    }
                ],
            }
        )

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "avouch", "version": version, "rules": rules}},
                "results": results,
            }
        ],
    }

    print(json.dumps(sarif, indent=2))


def render_diff_view(file_paths, function_reports=None, file_reports=None, class_reports=None):

    _set_font()
    print(_style("[CHANGED FILES]", _BOLD))
    print()

    _annotation_map = None
    _source_cache = {}
    if function_reports is not None or file_reports is not None or class_reports is not None:
        try:
            _annotation_map = _build_annotation_map(
                function_reports or [], file_reports or [], class_reports or []
            )
            for _fp in file_paths:
                try:
                    _source_cache[_fp] = Path(_fp).read_text(encoding="utf-8").splitlines()
                except Exception:
                    _source_cache[_fp] = []
        except Exception:
            _annotation_map = None
            _source_cache = {}

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

        _file_ann = _annotation_map.get(file_path) if _annotation_map else None
        if _file_ann is not None and (_file_ann["by_line"] or _file_ann["file_level"]):
            try:
                _render_diff_with_annotations(
                    hunks, labels, _file_ann, _source_cache.get(file_path, [])
                )
                continue
            except Exception:
                pass
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


def _build_annotation_map(function_reports, file_reports, class_reports):
    try:
        issues_by_file = {}
        for report in [*class_reports, *function_reports, *file_reports]:
            if not report.get("issues"):
                continue
            file_name = report.get("file", report["name"])
            bucket = issues_by_file.setdefault(file_name, [])
            for issue in report["issues"]:
                bucket.append(
                    (
                        report["name"],
                        report["kind"],
                        issue["message"],
                        issue["severity"],
                        issue.get("rule"),
                        report.get("line"),
                    )
                )
        result = {}
        for file_name, entries in issues_by_file.items():
            try:
                rows = _issue_rows(entries)
            except Exception:
                rows = []
            by_line = {}
            file_level = []
            for row in rows:
                _item, _rid, _rname, _metric, _is_err, _line, _msg = row
                if _line is None or _item == "file":
                    file_level.append(row)
                else:
                    by_line.setdefault(_line, []).append(row)
            result[file_name] = {"by_line": by_line, "file_level": file_level}
        return result
    except Exception:
        return {}


def _render_annotation(row, source_lines, orphan_line=None):
    try:
        item_name, rule_id, rule_name, _metric, is_error, line, message = row
        display_line = orphan_line if orphan_line is not None else line
        col = -1
        if orphan_line is None and source_lines and line and item_name != "file":
            try:
                if 1 <= line <= len(source_lines):
                    col = source_lines[line - 1].find(item_name)
            except Exception:
                col = -1
        base = _INDENT + _INDENT + "  "
        rule = rule_id or ""
        if orphan_line is not None:
            prefix = f"line {display_line}: "
            caret = "→"
            print(base + _style(caret, _BLUE) + " " + prefix + (_style(rule, _BLUE) + ": " if rule else "") + (_style(message, _RED) if is_error else _style(message, _DIM)))
            return
        if col != -1:
            caret = " " * col + "^" * len(item_name) if item_name and item_name != "file" else "→"
            print(base + _style(caret, _BLUE) + " " + (_style(rule, _BLUE) + ": " if rule else "") + (_style(message, _RED) if is_error else _style(message, _DIM)))
        else:
            caret = "→"
            print(base + _style(caret, _BLUE) + " " + (_style(rule, _BLUE) + ": " if rule else "") + (_style(message, _RED) if is_error else _style(message, _DIM)))
    except Exception:
        try:
            print(_INDENT + _INDENT + "  " + _style("→ ", _BLUE) + str(row))
        except Exception:
            pass


def _render_hunk_annotated(hunk, labels, by_line, source_lines):
    current_label = None
    for tag, line_number, text in hunk:
        if tag != "del":
            label = labels.get(line_number) if line_number is not None else None
            if label and label != current_label:
                print(_style(_INDENT + _INDENT + "  " + label, _DIM))
                current_label = label
        if tag == "add":
            print(_style(_INDENT + _INDENT + "+ " + text, _GREEN))
        elif tag == "del":
            print(_style(_INDENT + _INDENT + "- " + text, _RED))
        else:
            print(_INDENT + _INDENT + "  " + text)
        if tag != "del" and line_number is not None and line_number in by_line:
            for row in by_line[line_number]:
                _render_annotation(row, source_lines)


def _render_diff_with_annotations(hunks, labels, file_ann, source_lines):
    displayed = set()
    for hunk in hunks:
        for tag, ln, _ in hunk:
            if ln is not None:
                displayed.add(ln)
    for hunk in hunks:
        _render_hunk_annotated(hunk, labels, file_ann.get("by_line", {}), source_lines)
    for row in file_ann.get("file_level", []):
        _render_annotation(row, source_lines)
    orphan = [ln for ln in file_ann.get("by_line", {}) if ln not in displayed]
    if orphan:
        print(_style(_INDENT + _INDENT + f"  · {len(orphan)} finding(s) outside diff context:", _DIM))
        for ln in sorted(orphan):
            for row in file_ann["by_line"][ln]:
                _render_annotation(row, source_lines, orphan_line=ln)


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


def _render_premium(issues_by_file, file_reports, error_count, warning_count, suppressed, total_files):
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.columns import Columns
    from rich.rule import Rule
    console = Console()
    from importlib.metadata import version as _ver
    try:
        v = _ver("avouch")
    except Exception:
        v = "0.3.4"
    from rich.panel import Panel
    metrics = Text()
    metrics.append(f"{total_files}", style="bold")
    metrics.append(" files", style=f"dim {_MUTED}")
    metrics.append("  ·  ", style=f"dim {_BORDER}")
    metrics.append(f"{warning_count}", style=f"bold {_ACCENT}" if warning_count else "dim")
    metrics.append(" warn", style=f"dim {_MUTED}")
    metrics.append("  ·  ", style=f"dim {_BORDER}")
    metrics.append(f"{error_count}", style=f"bold {_ERROR}" if error_count else "dim")
    metrics.append(" err", style=f"dim {_MUTED}")
    if suppressed:
        metrics.append(f"  ·  +{suppressed} suppressed", style=f"dim {_MUTED} italic")
    metrics.justify = "center"
    from rich import box
    console.print(Panel(metrics, border_style="#6b6560", padding=(0,2), title=f"avouch {v}", title_align="left", expand=True, width=_LINE_WIDTH, box=box.SQUARE))



    rule_counts = {}
    rule_labels = {}
    file_order = sorted(issues_by_file)
    for file_name in file_order:
        try:
            source_lines = Path(file_name).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            source_lines = []
        console.print()
        console.print(Text(file_name, style=f"bold {_MUTED}") + Text(f"  ·  {len(issues_by_file[file_name])} finding{'s' if len(issues_by_file[file_name])!=1 else ''}", style="dim"))
        for item_name, rule_id, rule_name, metric, is_error, line, message in _issue_rows(issues_by_file[file_name]):
            key = rule_id or rule_name
            rule_counts[key] = rule_counts.get(key, 0) + 1
            rule_labels[key] = rule_name
            border = _ERROR if is_error else _ACCENT
            loc = f"{file_name}:{line or 1}"
            title = Text()
            title.append(loc, style="bold")
            title.append("  ")
            if rule_id:
                title.append(f" {rule_id} ", style=f"bold white on {border}")
                title.append(" ", style="")
            title.append(message, style=f"{_ERROR} bold" if is_error else "")
            code = ""
            caret_line = ""
            if source_lines and line and 1 <= line <= len(source_lines):
                head = max(line - 1, 1)
                tail = min(line + 1, len(source_lines))
                width = len(str(tail))
                lines = []
                for n in range(head, tail+1):
                    prefix = f"{n:>{width}} │ "
                    txt = source_lines[n-1]
                    if n == line and item_name != "file":
                        col = txt.find(item_name)
                        if col != -1:
                            caret = " " * (len(prefix) + col) + "^" * len(item_name)
                            caret_line = caret
                    lines.append(prefix + txt)
                code = "\n".join(lines)
                if caret_line:
                    code += "\n" + " " * width + " │ " + caret_line.strip()
            body = Text(message, style="") if not code else Text.from_markup(code, style=f"dim {_MUTED}") if False else None
            if code:
                panel_text = Text()
                panel_text.append(message + "\n", style=f"{_ERROR}" if is_error else f"{_MUTED}")
                panel_text.append(code, style=f"dim {_MUTED}")
                if caret_line:
                    pass
                console.print(Panel(panel_text, title=title, title_align="left", border_style=border, padding=(0,1), expand=False))
            else:
                console.print(Panel(Text(message, style=f"{_ERROR}" if is_error else ""), title=title, title_align="left", border_style=border, padding=(0,1), expand=False))
    if rule_counts:
        console.print()
        console.print(Rule(style=_BORDER))
        t = Table(show_header=False, box=None, padding=(0,1))
        t.add_column("rule", style=f"bold {_ACCENT}", justify="right", no_wrap=True)
        t.add_column("name", style=f"dim {_MUTED}")
        t.add_column("count", style="bold", justify="right")
        ordered = sorted(rule_counts, key=lambda k: (-rule_counts[k], k))
        for key in ordered:
            label = rule_labels[key]
            display = key if label==key else f"{key}  {label}" if key else label
            # split for table: if key prefix exists, show as two cols
            if key and label != key:
                t.add_row(key, label, str(rule_counts[key]))
            else:
                t.add_row("", label, str(rule_counts[key]))
        console.print(Text("BY RULE", style="bold dim"))
        console.print(t)
        if suppressed:
            console.print(Text(f"  +{suppressed} suppressed by baseline", style=f"dim {_MUTED}"))
    passing_files = [r["name"] for r in file_reports if r["name"] not in issues_by_file]
    if passing_files:
        console.print()
        from rich.panel import Panel
        from rich import box
        t = Text()
        for i, name in enumerate(passing_files[:18]):
            if i:
                t.append("  ·  ", style=f"dim {_MUTED}")
            t.append(f"✓ {name}", style=f"dim {_SUCCESS}")
        if len(passing_files) > 18:
            t.append(f"  ·  +{len(passing_files)-18} more", style=f"dim {_MUTED}")
        t.justify = "center"
        console.print(Panel(t, border_style="#6b6560", padding=(0,2), title=f"passed  ·  {len(passing_files)}", title_align="left", expand=True, width=_LINE_WIDTH, box=box.SQUARE))
    console.print()






def render_report(function_reports, file_reports, class_reports, suppressed=0):

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

        file_name = report.get("file", report["name"])
        item_name = report["name"]
        kind = report["kind"]

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

    if not issues_by_file:
        if _USE_COLOR:
            try:
                from rich.console import Console
                from rich.panel import Panel
                from rich.text import Text
                console = Console()
                console.print()
                body = Text()
                body.append("◉  All clean.", style=f"bold {_SUCCESS}")
                body.append(f"  —  {total_files} file{'s' if total_files!=1 else ''} passed", style=f"dim {_MUTED}")
                if suppressed:
                    body.append(f"  ·  +{suppressed} suppressed", style=f"dim {_MUTED}")
                hint = Text("no findings in changed files  ·  commit or push with confidence", style=f"dim {_MUTED} italic")
                console.print(Panel(Text.assemble(body, "\n", hint), border_style=_BORDER, padding=(1,2), title="[dim]avouch[/dim]", title_align="left", expand=False))
                console.print()
                return
            except Exception:
                pass
        print(_style("All clean.", _BOLD))
        return

    if _USE_COLOR:
        try:
            _render_premium(issues_by_file, file_reports, error_count, warning_count, suppressed, total_files)
            return
        except Exception:
            pass

    print(
        _style("AVOUCH", _BOLD)
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
        _render_rule_summary(rule_counts, rule_labels, suppressed)
    elif suppressed:
        print()
        print(_style("─" * _LINE_WIDTH, _DIM))
        print(_style(f"(+{suppressed} suppressed by baseline)", _DIM))

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


def _most_common_first(counts, key):
    return (-counts[key], key)


def _render_rule_summary(rule_counts, rule_labels, suppressed=0):

    ordered = sorted(rule_counts, key=lambda key: _most_common_first(rule_counts, key))

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

    if suppressed:
        print(_INDENT + _style(f"(+{suppressed} suppressed by baseline)", _DIM))


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