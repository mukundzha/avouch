"""
Terminal documentation rendered by `scrut --docs`.

Every statement here describes behavior implemented in this repository.
"""

import shutil
import sys

DOCS = """\
SCRUT - Git-aware AST code review for the Python you changed
===========================================================

WHAT IT DOES
------------
Scrut is a Git-aware static analysis CLI for Python. It asks Git which
files your next commit will touch, parses each changed .py file with the
standard ast module, and reports structural problems against limits you
configure in scrut.toml. No daemon, no network, no path lists to
maintain: the review set is the diff.

WORKFLOW
--------
Git repository -> changed .py files -> ast.parse -> rules -> findings

1. Load configuration: a scrut.toml in the current directory, if
   present, merged over the built-in defaults
   (src/scrut/config/loader.py, src/scrut/config/default.py).
2. Verify the working directory is a Git repository
   (git rev-parse --is-inside-work-tree). Otherwise print
   "error: no Git repository found" to stderr and exit 2
   (skipped with --not-git).
3. Compute the review set (src/scrut/git.py):
   - git diff HEAD --name-only        (staged + unstaged changes)
   - git diff --cached --name-only    (staged changes only, with --staged)
   - git ls-files --others --exclude-standard   (untracked files)
   - keep paths that are existing .py files, not generated files
     (src/scrut/utility/is_generated.py), and not covered by ignore
     paths (src/scrut/utility/is_ignored.py).
   If nothing remains, print "error: nothing to review" to stderr and
   exit 2.
4. Parse each reviewable file with ast.parse and walk the tree once
   (src/scrut/analyzer.py). A file that cannot be read or parsed
   becomes an ERROR finding; the rest of the review continues.
5. Run the rules enabled by the config against functions, async
   functions, classes, and files (see REVIEW RULES below).
6. Print the report: human-readable by default (suppressed with
   --quiet), JSON with --json (src/scrut/report.py).
7. Exit status: 0 = clean, 1 = findings reported, 2 = Scrut could
   not run.

ARCHITECTURE
------------
A local CLI: one Python process, no daemons or network. Modules in
execution order:

    cli.py (scrut.cli:main)          argparse, orchestration, exit codes
      |-- config/loader.py           scrut.toml merged over defaults
      |-- git.py                     repository check + candidate files
      |   `-- utility/is_generated.py, utility/is_ignored.py  filters
      |-- analyzer.py                read -> ast.parse -> ast.walk
      |   `-- rules/*.py             one analyze(node, limits) per rule
      |-- report.py                  terminal report / JSON / diff view
      `-- utility/docs.py            this text

Only cli.py calls the pipeline modules; none of them imports cli.py.
report.py imports git.py for the --changed diff view, and analyzer.py
imports every rules module. --docs and --version return before config
loading, so no Git or analysis code runs.

INSTALLATION
------------
Requires Python 3.10+ (ast.Match, tomllib) and git on PATH.

    pip install scrut

or from source:

    git clone https://github.com/mukundzha/scrut.git
    cd scrut
    pip install -e .

Both register the `scrut` console script (scrut.cli:main).

USAGE
-----
Run inside a Git repository after making changes, before pushing:

    scrut
    scrut --json
    scrut --ignore-path tests --ignore-path migrations

Scrut takes no target path argument: the review set is defined by Git,
not by the command line.

    scrut --help        argparse help for every option
    scrut --docs        this documentation; exits without reviewing
    scrut --version     print the version and exit
    scrut --verbose     step-by-step review details on stderr
    scrut --quiet       suppress the normal report; errors and exit codes are unchanged
    scrut --changed     show added/deleted lines of changed files instead of the report
    scrut --staged      review only files with staged Git changes
    scrut --all-files   review every eligible Python file, not just the diff
    scrut --not-git     review every eligible .py file on disk; Git is not required

Only one of --changed, --staged, and --all-files may be given; the
output flags --json, --verbose, and --quiet combine with any scope.
--not-git cannot be combined with --changed or --staged, which require
Git history.

CONFIGURATION
-------------
Configuration lives in scrut.toml in the current working directory
(no upward search). It is optional and partial: any subset is merged
over the built-in defaults. A malformed file raises instead of being
silently ignored.

Sections:

    [limits]        numeric thresholds per rule
    [rules]         on/off toggle per rule (boolean, all default true)
    ignore_paths    top-level list of repo-relative paths to skip

Ignore paths match whole path components: "tests" skips tests/ and
tests/x.py but not tests.py. A "." ignores the whole repository.

[limits] keys with their defaults (src/scrut/config/default.py):

    max_parameters            5    parameters per function (SCR014)
    max_nesting               5    block nesting depth (SCR013)
    max_function_lines      300    function line span (SCR012)
    max_class_lines         200    class line span (SCR010)
    max_file_lines         1000    file line count (SCR011)
    max_complexity           40    cyclomatic complexity, funcs+classes
    max_boolean_conditions    5    operands in one and/or chain (SCR003)
    max_if_chain              5    if/elif chain length (SCR007)
    max_local_variables      30    distinct assigned names (SCR009)
    max_return_statements     6    returns per function (SCR016)
    max_lambda_nodes         10    AST nodes in a lambda body (SCR008)
    max_large_comprehensions 40    AST nodes in a comprehension (SCR005)

A rule whose limit key is missing falls back to a default hardcoded in
its own module, so a partial [limits] never turns a rule off. Every
limit key above is present in DEFAULT_LIMITS, so all of them are tunable
from scrut.toml.

[rules] toggles (all default true):

    async_without_await         bare_except
    max_boolean_conditions      detect_duplicateb
    max_large_comprehensions    empty_except
    max_if_else_chain           max_lambda_nodes
    max_local_variables         max_class_lines
    max_file_lines              max_function_lines
    max_nesting                 max_parameters
    nested_function             max_return_statements
    max_complexity

Setting a toggle to false disables that rule's findings.

Observe whether the file was loaded with --verbose: the first
diagnostics line prints "config: scrut.toml, N ignore path(s)" (or
"config: defaults (no scrut.toml), 0 ignore path(s)" without a file).

Malformed TOML or a non-list ignore_paths prints
"error: invalid scrut.toml configuration: ..." and exits 2. Unknown
keys are accepted and ignored silently - a typo is silently
ineffective. Limit values are not type-checked: a non-numeric limit
fails at analysis time with an internal error (exit 2).

The CLI only appends --ignore-path to ignore_paths; there is no flag
for [limits] or [rules]. Configuration applies equally to every review
mode (--changed, --staged, --all-files) and output mode (--json,
--quiet, --verbose). Severity is not configurable: rule findings are
WARNING; ERROR is reserved for files that cannot be read or parsed.

Example - the exact scrut.toml this repository lives by:

    ignore_paths = ["tests"]

    [limits]
    max_parameters = 5
    max_nesting = 5
    max_function_lines = 300
    max_class_lines = 200
    max_file_lines = 1000
    max_complexity = 40
    max_boolean_conditions = 5
    max_if_chain = 5
    max_local_variables = 30
    max_return_statements = 6
    max_lambda_nodes = 10
    max_large_comprehensions = 40

    [rules]
    max_parameters = true
    max_nesting = true
    max_function_lines = true
    max_class_lines = true
    max_file_lines = true
    max_complexity = true
    max_boolean_conditions = true
    max_local_variables = true
    max_return_statements = true
    max_lambda_nodes = true
    max_large_comprehensions = true

REVIEW RULES
------------
Every rule finding is a WARNING. ERROR findings exist only for files
that cannot be read or parsed. Rules with a threshold render
"measured/limit" (e.g. 6/5); presence rules render "detected".

    SCR001  async function without await
            An "async def" whose body contains no "await" runs
            synchronously at event-loop cost; use a plain function.
            scope: async functions only.

    SCR002  bare except
            An "except:" handler catches every exception, including
            KeyboardInterrupt and SystemExit.
            scope: functions.

    SCR003  boolean expression too complex
            One and/or chain with too many operands; nested chains sum,
            so "a and (b or c)" scores 3.
            config: max_boolean_conditions (5). scope: funcs + classes.

    SCR004  duplicate branch (functions)
    SCR006  duplicate branch (classes)
            if/elif branches with identical bodies - copy-paste or a
            condition that never varies. The trailing else body is not
            compared. Two rule IDs implement the same detection:
            SCR004 (detect_duplicateb) runs on functions, SCR006
            (empty_except) on functions and classes.
            scope: SCR004 funcs; SCR006 funcs + classes.

    SCR005  large comprehension
            A list/set/dict comprehension or generator expression with
            more AST nodes than the limit.
            config: max_large_comprehensions (10). scope: functions.

    SCR007  long if/elif chain
            One if/elif chain longer than the limit.
            config: max_if_chain (5). scope: funcs + classes.

    SCR008  lambda too complex
            A lambda whose body has more AST nodes than the limit.
            config: max_lambda_nodes (5). scope: functions.

    SCR009  too many local variables
            More distinct assigned names than the limit; measured on
            plain assignment targets only. Assignments inside nested
            functions count toward the enclosing function's total.
            config: max_local_variables (15). scope: functions.

    SCR010  class too large
            Class line span exceeds max_class_lines (200).

    SCR011  file too large
            File line count exceeds max_file_lines (400).

    SCR012  function too long
            Function line span exceeds max_function_lines (50).

    SCR013  nesting too deep
            Maximum depth of block nodes (if/for/async for/while/with/
            async with/try/match) exceeds max_nesting (4).
            Comprehensions, lambdas, and nested defs add no depth;
            sibling blocks do not stack - the metric is maximum depth,
            not block count.

    SCR014  too many parameters
            Declared positional/keyword parameters exceed
            max_parameters (5). *args and **kwargs are not counted.

    SCR015  nested function definition
            A function defined inside another function, recreated
            inside the outer call. Only plain defs are flagged;
            a nested async def is not.
            scope: functions.

    SCR016  too many return statements
            More "return" statements than max_return_statements (3).
            Returns inside nested functions count toward the enclosing
            function's total.
            scope: functions.

    (no id) function or class too complex
            McCabe cyclomatic complexity: base 1, plus 1 for each
            if/for/async for/while/try/except handler/match/ternary/
            assert/with/async with and each and/or chain - a chain
            counts 1 no matter how many operands it combines, so
            "a and (b or c)" adds 2; summed over the whole subtree.
            Exceeds max_complexity (10).
            scope: funcs + classes.

FINDINGS AND OUTPUT
-------------------
Human report (colors only when stdout is a TTY):

    scrut [Review Summary]
    ╔═══════════════════════════════════════╗
    ║ 🟡 2 warnings │ 🟢 1 passed │ 📊 3 funcs checked ║
    ╚═══════════════════════════════════════╝

    [NEEDS REVIEW]
    ╭─ 🛑 src/app.py (2)
    │  Component  Kind  Rule                Metric
    │  ───────────────────────────────────────
    │  handle     func  Too many parameters  6/5
    │  <file>     file  File too large       41/50

    [PASSING]
    ✓ src/util.py  ✓ src/parser.py

Components are functions, classes, or "<file>"; kinds are func, class,
file. Identical (component, rule) rows are deduplicated per file, and
file-level rows sort first. Long rule names are truncated with "..." so
lines never wrap. The passing grid collapses to at most a few lines,
with a "[+N more]" note when it overflows. SCRUT_FONT=name is an
opt-in OSC 50 font switch honored only by capable terminals.

JSON (--json) prints a single document on stdout:

    {
      "version": 1,
      "tool": "scrut",
      "violations": [
        {
          "rule": "SCR014",
          "severity": "WARNING",
          "message": "Too many parameters (6/5). Group related "
                     "parameters into a data class or dictionary.",
          "file": "buggy.py",
          "name": "extra",
          "kind": "func",
          "line": 4
        }
      ],
      "summary": {
        "total": 1,
        "errors": 0,
        "warnings": 1,
        "files_with_violations": 1
      }
    }

Each violation carries its rule id (or a label derived from the
message when the rule has none), severity, message, file, component
name, kind, and the line the finding refers to (null for file-level
findings). "violations" is empty on a clean run. "version" is the
schema version and "tool" identifies the emitter, so consumers can
verify what produced the document. Output is deterministic: the same
input always produces the same JSON, with no colors, timestamps, or
diagnostics mixed in. Exit codes are the same in both modes: 0 clean,
1 findings, 2 cannot run.

EXAMPLES
--------
    # before pushing, inside the repository
    scrut

    # JSON for CI or tooling
    scrut --json

    # skip a path, e.g. a tests directory
    scrut --ignore-path tests

    # outside a Git repository
    scrut
    error: no Git repository found
    hint: run Scrut from inside a Git repository   (exit 2)

    # no changed Python files in a clean checkout (as in CI)
    scrut
    error: nothing to review
    hint: nothing changed vs HEAD (CI checkouts are clean); use --all-files for a full review   (exit 2)

    # a clean run
    scrut
    All clean.                            (exit 0)

PROJECT
-------
Source:  https://github.com/mukundzha/scrut
Issues:  https://github.com/mukundzha/scrut/issues
License: MIT (LICENSE)
Runtime: Python standard library (ast, tomllib) plus three git
         subprocess calls; pyproject.toml declares rich>=14.0.0, which
         the current code does not import.
Docs of record: README.md at the repository root.
"""

MENU = "H)elp  G)o  M)ain  Q)uit"


def _hint_box(text):
    inner = f" {text} "
    edge = "─" * len(inner)
    return f"┌{edge}┐\r\n│{inner}│\r\n└{edge}┘\r\n"


def render_docs():
    """Show the built-in documentation; interactive in a real terminal."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(DOCS)
        return
    try:
        import termios
        import tty
    except ImportError:
        print(DOCS)
        return
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        _browse()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _browse():
    doc_lines, spans = _section_spans()
    while _doc_page((0, len(doc_lines)), "main screen", spans) != "quit":
        pass


def _section_spans():
    lines = DOCS.splitlines()
    starts = []
    for i in range(len(lines) - 1):
        nxt = lines[i + 1]
        if nxt and set(nxt) <= set("=-") and any(c.isalpha() for c in lines[i]):
            starts.append(i)
    spans = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        spans.append((lines[start].strip(), start, end))
    return lines, spans


def _doc_page(span, label, spans):
    return _page(DOCS.splitlines(), span, label, spans)


def _page(lines, span, label, spans):
    start, end = span
    width, height = shutil.get_terminal_size((80, 24))
    body = max(height - 3, 5)
    pos = start
    hint = False
    while True:
        _clear(width)
        current = (pos - start) // body + 1
        total = max((end - start + body - 1) // body, 1)
        sys.stdout.write(f"{label} · page {current} of {total}\r\n")
        shown = body - 3 if hint else body
        for line in lines[pos:pos + shown]:
            sys.stdout.write(line + "\r\n")
        if hint:
            sys.stdout.write(_hint_box("press space to scroll down"))
        _footer(width)
        key = sys.stdin.read(1)
        if key in "qQ" or key == "":
            return "quit"
        if key in "hH":
            hint = True
            continue
        if key in "gG":
            target = _go_prompt(spans, width, height)
            if target is not None:
                _doc_page((target[1], target[2]), target[0].lower(), spans)
            return
        if key in "mM":
            return
        pos += body
        hint = False
        if pos >= end:
            return


def _go_prompt(spans, width, height):
    _clear(width)
    sys.stdout.write("Sections\r\n========\r\n")
    for i, (name, _, _) in enumerate(spans, 1):
        sys.stdout.write(f"{i:>2}. {name}\r\n")
    sys.stdout.write("Go to (number or name): ")
    sys.stdout.flush()
    answer = _read_line()
    if not answer:
        return None
    if answer.isdigit():
        try:
            return spans[int(answer) - 1]
        except IndexError:
            return None
    want = answer.lower()
    for span in spans:
        if span[0].lower().startswith(want):
            return span
    return None


def _read_line():
    chars = []
    while True:
        ch = sys.stdin.read(1)
        if ch in ("\r", "\n"):
            sys.stdout.write("\r\n")
            sys.stdout.flush()
            return "".join(chars)
        if ch in ("\x7f", "\b"):
            if chars:
                chars.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if ch in ("", "\x04"):
            return "".join(chars)
        chars.append(ch)
        sys.stdout.write(ch)
        sys.stdout.flush()


def _clear(width):
    sys.stdout.write("\r\033[H\033[J")
    sys.stdout.flush()


def _footer(width):
    sys.stdout.write("─" * min(width, 80) + "\r\n")
    menu = MENU
    if len(menu) > width:
        menu = " ".join(menu.split())
    sys.stdout.write(menu[:width] + "\r\n")