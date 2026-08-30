"""
Terminal documentation rendered by `avouch --docs`.

Every statement here describes behavior implemented in this repository.
"""

import shutil
import sys
import textwrap

RULES = {
    "SCR001": {
        "name": "async function without await",
        "description": 'An "async def" whose body contains no "await" runs synchronously at event-loop cost; use a plain function.',
        "why": "Async functions without await waste event-loop overhead.",
        "example_bad": "async def fetch():\n    return 42",
        "example_good": "def fetch():\n    return 42",
        "config_key": "async_without_await",
        "scope": "async functions only",
        "severity": "WARNING",
    },
    "SCR002": {
        "name": "bare except",
        "description": 'An "except:" handler catches every exception, including KeyboardInterrupt and SystemExit.',
        "why": "Catches too much; hide interrupts.",
        "example_bad": "try:\n    do()\nexcept:\n    pass",
        "example_good": "try:\n    do()\nexcept ValueError:\n    pass",
        "config_key": "bare_except",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR003": {
        "name": "boolean expression too complex",
        "description": 'One and/or chain with too many operands; nested chains sum, so "a and (b or c)" scores 3.',
        "why": "Hard to reason; split condition.",
        "example_bad": "if a and b and c and d and e and f:\n    pass",
        "example_good": "if all([a, b, c]):\n    pass",
        "config_key": "max_boolean_conditions",
        "limit_key": "max_boolean_conditions",
        "scope": "funcs + classes",
        "severity": "WARNING",
    },
    "SCR004": {
        "name": "duplicate branch (functions)",
        "description": "if/elif branches with identical bodies - copy-paste or condition never varies. Trailing else not compared.",
        "why": "Duplicated logic suggests bug.",
        "example_bad": "if x == 1:\n    do()\nelif x == 2:\n    do()",
        "example_good": "if x in (1, 2):\n    do()",
        "config_key": "detect_duplicateb",
        "scope": "funcs",
        "severity": "WARNING",
    },
    "SCR005": {
        "name": "large comprehension",
        "description": "A list/set/dict comprehension or generator expression with more AST nodes than the limit.",
        "why": "Unreadable; extract helper.",
        "example_bad": "[x for x in data if cond for y in x for z in y]",
        "example_good": "result = []\nfor x in data:\n    if cond:\n        result.append(x)",
        "config_key": "max_large_comprehensions",
        "limit_key": "max_large_comprehensions",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR006": {
        "name": "duplicate branch (classes)",
        "description": "if/elif branches with identical bodies - copy-paste or condition never varies. Trailing else not compared.",
        "why": "Duplicated logic suggests bug.",
        "example_bad": "if x == 1:\n    do()\nelif x == 2:\n    do()",
        "example_good": "if x in (1, 2):\n    do()",
        "config_key": "empty_except",
        "scope": "funcs + classes",
        "severity": "WARNING",
    },
    "SCR007": {
        "name": "long if/elif chain",
        "description": "One if/elif chain longer than the limit.",
        "why": "Too many branches; use dispatch.",
        "example_bad": "if a:\n    pass\nelif b:\n    pass\nelif c:\n    pass\nelif d:\n    pass\nelif e:\n    pass\nelif f:\n    pass",
        "example_good": "handlers = {a: fn1, b: fn2}\nhandlers.get(x, default)()",
        "config_key": "max_if_else_chain",
        "limit_key": "max_if_chain",
        "scope": "funcs + classes",
        "severity": "WARNING",
    },
    "SCR008": {
        "name": "lambda too complex",
        "description": "A lambda whose body has more AST nodes than the limit.",
        "why": "Unreadable; use def.",
        "example_bad": "fn = lambda x: (x and y or z and w and v)",
        "example_good": "def fn(x):\n    return x and y",
        "config_key": "max_lambda_nodes",
        "limit_key": "max_lambda_nodes",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR009": {
        "name": "too many local variables",
        "description": "More distinct assigned names than the limit; measured on plain assignment targets only. Assignments inside nested functions count toward enclosing.",
        "why": "Too much state; split function.",
        "example_bad": "def f():\n    a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u=v=w=x=y=z=1",
        "example_good": "def f():\n    data = {}\n    return data",
        "config_key": "max_local_variables",
        "limit_key": "max_local_variables",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR010": {
        "name": "class too large",
        "description": "Class line span exceeds max_class_lines (200).",
        "why": "Too large; split responsibilities.",
        "example_bad": "class Big:\n    # 250 lines",
        "example_good": "class Small:\n    pass",
        "config_key": "max_class_lines",
        "limit_key": "max_class_lines",
        "scope": "classes",
        "severity": "WARNING",
    },
    "SCR011": {
        "name": "file too large",
        "description": "File line count exceeds max_file_lines (1000).",
        "why": "Split into modules.",
        "example_bad": "# 1200 line file",
        "example_good": "# split file",
        "config_key": "max_file_lines",
        "limit_key": "max_file_lines",
        "scope": "files",
        "severity": "WARNING",
    },
    "SCR012": {
        "name": "function too long",
        "description": "Function line span exceeds max_function_lines (300).",
        "why": "Too long; extract helpers.",
        "example_bad": "def f():\n    # 400 lines",
        "example_good": "def f():\n    helper()",
        "config_key": "max_function_lines",
        "limit_key": "max_function_lines",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR013": {
        "name": "nesting too deep",
        "description": "Maximum depth of block nodes (if/for/async for/while/with/async with/try/match) exceeds max_nesting (5). Comprehensions, lambdas, nested defs add no depth; sibling blocks do not stack.",
        "why": "Deep nesting hard to follow.",
        "example_bad": "if a:\n    if b:\n        if c:\n            if d:\n                if e:\n                    if f:\n                        pass",
        "example_good": "if not a: return\nif not b: return",
        "config_key": "max_nesting",
        "limit_key": "max_nesting",
        "scope": "funcs+classes",
        "severity": "WARNING",
    },
    "SCR014": {
        "name": "too many parameters",
        "description": "Declared positional/keyword parameters exceed max_parameters (5). *args and **kwargs are not counted.",
        "why": "Too many args; group into dataclass/dict.",
        "example_bad": "def f(a, b, c, d, e, f):\n    pass",
        "example_good": "def f(opts):\n    pass",
        "config_key": "max_parameters",
        "limit_key": "max_parameters",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR015": {
        "name": "nested function definition",
        "description": "A function defined inside another function, recreated inside the outer call. Only plain defs are flagged; a nested async def is not.",
        "why": "Recreated per call; hoist.",
        "example_bad": "def outer():\n    def inner():\n        pass",
        "example_good": "def inner():\n    pass\ndef outer():\n    inner()",
        "config_key": "nested_function",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR016": {
        "name": "too many return statements",
        "description": 'More "return" statements than max_return_statements (6). Returns inside nested functions count toward enclosing.',
        "why": "Too many exits; simplify.",
        "example_bad": "def f(x):\n    if a: return 1\n    if b: return 2\n    if c: return 3\n    if d: return 4\n    if e: return 5\n    if f: return 6\n    if g: return 7",
        "example_good": "def f(x):\n    return mapping.get(x, 0)",
        "config_key": "max_return_statements",
        "limit_key": "max_return_statements",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR017": {
        "name": "mutable default argument",
        "description": "A default parameter value that is a mutable literal ([], {}, {..}) or a mutable constructor call (list(), dict(), set(), bytearray(), defaultdict(), OrderedDict()). Defaults are evaluated once at definition time, so the same object is shared across every call that omits the argument. Use None and construct inside.",
        "why": "Shared mutable default bug.",
        "example_bad": "def f(items=[]):\n    items.append(1)",
        "example_good": "def f(items=None):\n    if items is None:\n        items = []",
        "config_key": "mutable_default_args",
        "scope": "functions",
        "severity": "WARNING",
    },
    "SCR019": {
        "name": "subprocess shell execution",
        "description": "A subprocess call with shell=True executes through a shell and can allow command injection when input is influenced by users.",
        "why": "Shell execution expands command-injection risk.",
        "example_bad": "subprocess.run(command, shell=True)",
        "example_good": "subprocess.run([program, argument])",
        "config_key": "shell_true",
        "scope": "functions",
        "severity": "ERROR",
    },
    "SCR020": {
        "name": "dynamic code execution",
        "description": "A call to eval() or exec() executes dynamically supplied Python code and can run untrusted input.",
        "why": "Untrusted code execution can compromise the process.",
        "example_bad": "eval(user_input)",
        "example_good": "operations[user_input]()",
        "config_key": "dynamic_code",
        "scope": "functions",
        "severity": "ERROR",
    },
    "CPLX": {
        "name": "function or class too complex",
        "description": "McCabe cyclomatic complexity: base 1, plus 1 for each if/for/async for/while/try/except handler/match/ternary/assert/with/async with and each and/or chain - a chain counts 1 no matter how many operands it combines, so \"a and (b or c)\" adds 2; summed over whole subtree. Exceeds max_complexity (40).",
        "why": "Complex branching; extract.",
        "example_bad": "def f(x):\n    if a and b or c:\n        for y in x:\n            if y:\n                try:\n                    do()\n                except:\n                    pass",
        "example_good": "def f(x):\n    helper(x)",
        "config_key": "max_complexity",
        "limit_key": "max_complexity",
        "scope": "funcs + classes",
        "severity": "WARNING",
    },
}


def _format_rule(rule_id, spec):
    lines = []
    name = spec["name"]
    lines.append(f"    {rule_id}  {name}")
    desc = spec["description"]
    for w in textwrap.wrap(desc, width=76):
        lines.append(f"            {w}")
    scope = spec.get("scope")
    if scope:
        lines.append(f"            scope: {scope}.")
    cfg = spec.get("config_key")
    limit = spec.get("limit_key")
    if limit:
        lines.append(f"            config: {limit} ({spec.get('severity','WARNING')}).")
    elif cfg:
        lines.append(f"            config: {cfg}.")
    why = spec.get("why")
    if why:
        lines.append(f"            why: {why}")
    bad = spec.get("example_bad")
    good = spec.get("example_good")
    if bad:
        lines.append(f"            Bad:")
        for l in bad.splitlines():
            lines.append(f"                {l}")
    if good:
        lines.append(f"            Good:")
        for l in good.splitlines():
            lines.append(f"                {l}")
    lines.append("")
    return "\n".join(lines)


def _rules_section():
    parts = []
    parts.append("REVIEW RULES")
    parts.append("------------")
    parts.append('Every rule finding is a WARNING. ERROR findings exist only for files')
    parts.append('that cannot be read or parsed. Rules with a threshold render')
    parts.append('"measured/limit" (e.g. 6/5); presence rules render "detected".')
    parts.append("")
    for rid in sorted(RULES):
        if rid == "CPLX":
            parts.append("    (no id) function or class too complex")
            spec = RULES[rid]
            for w in textwrap.wrap(spec["description"], width=76):
                parts.append(f"            {w}")
            parts.append(f"            scope: {spec['scope']}.")
            parts.append("")
            continue
        parts.append(_format_rule(rid, RULES[rid]).rstrip())
    return "\n".join(parts)


def _build_docs():
    header = """AVOUCH - Git-aware AST code review for the Python you changed
===========================================================

WHAT IT DOES
------------
Avouch is a Git-aware static analysis CLI for Python. It asks Git which
files your next commit will touch, parses each changed .py file with the
standard ast module, and reports structural problems against limits you
configure in avouch.toml. No daemon, no network, no path lists to
maintain: the review set is the diff.

WORKFLOW
--------
Git repository -> changed .py files -> ast.parse -> rules -> findings

1. Load configuration: avouch.toml discovered by walking upward from
   CWD to filesystem root, if present, merged over built-in defaults
   (src/avouch/config/loader.py, src/avouch/config/default.py).
2. Verify the working directory is a Git repository
   (git rev-parse --is-inside-work-tree). Otherwise print
   "error: no Git repository found" to stderr and exit 2
   (skipped with --not-git).
3. Compute the review set (src/avouch/git.py):
   - git diff HEAD --name-only        (staged + unstaged changes)
   - git diff --cached --name-only    (staged changes only, with --staged)
   - git ls-files --others --exclude-standard   (untracked files)
   - keep paths that are existing .py files, not generated files
     (src/avouch/utility/is_generated.py), and not covered by ignore
     paths (src/avouch/utility/is_ignored.py).
   If nothing remains, print "error: nothing to review" to stderr and
   exit 2.
4. Parse each reviewable file with ast.parse and walk the tree once,
   cached per file (src/avouch/analyzer.py, src/avouch/utility/walk.py).
   A file that cannot be read or parsed becomes an ERROR finding; the
   rest of the review continues.
5. Run the rules enabled by the config against functions, async
   functions, classes, and files (see REVIEW RULES below).
6. Baseline filter: load .avouch/baseline.json (mtime cache) and filter
   before render/exit; --no-baseline bypasses; --verbose logs suppressed;
   BY RULE shows (+N suppressed).
7. Print the report: human-readable by default (suppressed with
   --quiet), JSON with --json (src/avouch/report.py).
8. Exit status: 0 = clean, 1 = findings reported, 2 = Avouch could
   not run.

ARCHITECTURE
------------
A local CLI: one Python process, no daemons or network. Modules in
execution order:

    cli.py (avouch.cli:main)          argparse, orchestration, exit codes
      |-- config/loader.py           avouch.toml merged over defaults
      |-- git.py                     repository check + candidate files
      |   `-- utility/is_generated.py, utility/is_ignored.py  filters
      |-- analyzer.py                read -> ast.parse -> walk cache
      |   `-- rules/*.py             one analyze(node, limits) per rule
      |       `-- utility/walk.py    ast.walk cached per file
      |-- baseline.py                load/filter/write baseline
      |-- report.py                  terminal report / JSON / diff view
      `-- utility/docs.py            this text

Only cli.py calls the pipeline modules; none of them imports cli.py.
report.py imports git.py for the --changed diff view, and analyzer.py
imports every rules module. --docs and --version return before config
loading, so no Git or analysis code runs.

INSTALLATION
------------
Requires Python 3.10+ (ast.Match, tomllib) and git on PATH.

    pip install avouch

or from source:

    git clone https://github.com/mukundzha/avouch.git
    cd avouch
    pip install -e .

Both register the `avouch` console script (avouch.cli:main).

USAGE
-----
Run inside a Git repository after making changes, before pushing:

    avouch
    avouch --json
    avouch --ignore-path tests --ignore-path migrations

Avouch takes no target path argument: the review set is defined by Git,
not by the command line.

    avouch --help        help
    avouch --docs        this docs; exit without review
    avouch --version     version
    avouch --verbose     details on stderr
    avouch --quiet       no report; exit code only
    avouch --watch       watch and re-run on change (polling, Ctrl+C)
    avouch --changed     diff view of changed files
    avouch --staged      staged only
    avouch --all-files   every eligible file
    avouch --not-git     walk CWD; no Git needed
    avouch baseline      snapshot findings to .avouch/baseline.json
    avouch --no-baseline ignore baseline
    avouch rule SCR002   show one rule (or list all with no arg)

Only one of --changed/--staged/--all-files; --json/--verbose/--quiet/--watch combine with any scope;
--not-git conflicts with --changed/--staged; --watch conflicts with --json/--format/--list-changed/--display.

CONFIGURATION
-------------
Configuration is avouch.toml discovered by walking upward from CWD to
filesystem root (so a run from tests/ uses repo-root avouch.toml).
Optional and partial: any subset merged over built-in defaults. Malformed
or invalid values raise instead of being silently ignored.

Sections:

    [limits]        numeric thresholds per rule
    [rules]         on/off toggle per rule (boolean, all default true)
    ignore_paths    top-level list of repo-relative paths to skip

Ignore paths match whole path components: "tests" skips tests/ and
tests/x.py but not tests.py. A "." ignores the whole repository.

[limits] keys with their defaults (src/avouch/config/default.py):

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
from avouch.toml.

[rules] toggles (all default true):

    async_without_await         bare_except
    max_boolean_conditions      detect_duplicateb
    max_large_comprehensions    empty_except
    max_if_else_chain           max_lambda_nodes
    max_local_variables         max_class_lines
    max_file_lines              max_function_lines
    max_nesting                 max_parameters
    nested_function             max_return_statements
    mutable_default_args        max_complexity

Setting a toggle to false disables that rule's findings.

Check load with --verbose: "config: <resolved-path>, N ignore path(s)"
(or "config: defaults (no avouch.toml), 0 ignore path(s)" without a file).

Malformed TOML, non-list ignore_paths, or invalid limits/rules prints
"error: invalid avouch.toml configuration: ..." and exits 2. Unknown
keys are ignored silently. Limits must be positive integers, rules
booleans, ignore_paths list of strings (e.g. limits.max_parameters
must be a positive integer; got "eight").

The CLI only appends --ignore-path to ignore_paths; there is no flag
for [limits] or [rules]. Configuration applies equally to every review
mode (--changed, --staged, --all-files) and output mode (--json,
--quiet, --verbose). Severity is not configurable: rule findings are
WARNING; ERROR is reserved for files that cannot be read or parsed.

Example - the exact avouch.toml this repository lives by:

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
    mutable_default_args = true

BASELINE
--------
Snapshot hides legacy: `avouch baseline` runs a full review and writes
`.avouch/baseline.json` `{"version":1,"findings":[{"rule","file","name","line"}]}`
with fingerprint `rule+file+name+line` (moving a function re-flags). Commit
it like `avouch.toml`. Next runs filter before render and before exit code;
`--no-baseline` bypasses; `--verbose` logs suppressed count and `BY RULE`
shows `(+N suppressed)`. Idempotent, recomputes from scratch. Malformed
JSON or wrong version prints `error: invalid baseline:` and exits 2. No file
means no suppression.

"""
    findings = """
FINDINGS AND OUTPUT
-------------------
Human report (colors only when stdout is a TTY, premium blocks on TTY, plain on pipe):

    ┌─ avouch 0.3.4 ───────────────────────────────────────────────────────────────┐
    │                        2 files  ·  4 warn  ·  0 err                        │
    └──────────────────────────────────────────────────────────────────────────────┘

    src/app.py:1: SCR002: Bare except detected. Catch a specific
    exception instead, e.g. except ValueError:.
      │
    1 │ def connect(host, port, user, password, db, timeout):
      │     ^^^^^^^ SCR002
    2 │     try:
      │

    src/app.py:1: SCR014: Too many parameters (6/5). Group related
    parameters into a data class or dictionary.
      │
    1 │ def connect(host, port, user, password, db, timeout):
      │     ^^^^^^^ SCR014
    2 │     try:
      │

    BY RULE

      SCR002 Bare except          1
      SCR014 Too many parameters  1

    PASSED
    ✓ src/util.py

The header counts every finding per file and severity; when stdout is
piped it is the only line that stands apart. Findings render
compiler-style: a "file:line" header with the rule id and full
message, the offending code region with dimmed line numbers, and a
caret under the flagged name (rule id in blue on a TTY). Identical
(component, rule) findings are deduplicated per file, so the header
count can exceed the row count when two rule ids map to the same
detection (SCR004/SCR006). The BY RULE summary lists deduplicated
counts per rule, most common first, and appears only when findings
exist. The passing grid collapses to at most a few lines, with a
"[+N more]" note when it overflows. AVOUCH_FONT=name is an opt-in
OSC 50 font switch honored only by capable terminals.

JSON (--json) prints a single document on stdout:

    {
      "version": 1,
      "tool": "avouch",
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
    avouch

    # JSON for CI or tooling
    avouch --json

    # skip a path, e.g. a tests directory
    avouch --ignore-path tests

    # per-rule help
    avouch rule SCR002
    avouch rule

    # outside a Git repository
    avouch
    error: no Git repository found
    hint: run Avouch from inside a Git repository, or use --not-git to review files without Git   (exit 2)

    # no changed Python files in a clean checkout (as in CI)
    avouch
    error: nothing to review
    hint: nothing changed vs HEAD (CI checkouts are clean); use --all-files for a full review   (exit 2)

    # a clean run
    avouch
    All clean.                            (exit 0)

PROJECT
-------
Source:  https://github.com/mukundzha/avouch
Issues:  https://github.com/mukundzha/avouch/issues
License: MIT (LICENSE)
Runtime: Python standard library (ast, tomllib) plus three git
         subprocess calls; pyproject.toml declares rich>=14.0.0, which
         the current code does not import.
Docs of record: README.md at the repository root.
"""
    return header + _rules_section() + findings


DOCS = _build_docs()

MENU = "H)elp  G)o  M)ain  Q)uit"


def render_rule(rule_id):
    rid = rule_id.upper()
    if rid not in RULES:
        return None
    spec = RULES[rid]
    lines = []
    lines.append(f"{rid}  {spec['name']}")
    lines.append("-" * len(f"{rid}  {spec['name']}"))
    lines.append("")
    lines.append(spec["description"])
    lines.append("")
    lines.append(f"Scope: {spec.get('scope','')}")
    if spec.get("limit_key"):
        lines.append(f"Config: {spec['limit_key']} (limit {spec['limit_key']}) / toggle {spec['config_key']} (default true)")
    else:
        lines.append(f"Config: {spec['config_key']} (default true)")
    lines.append(f"Severity: {spec.get('severity','WARNING')}")
    lines.append("")
    lines.append("Bad:")
    for l in spec.get("example_bad","").splitlines():
        lines.append(f"  {l}")
    lines.append("")
    lines.append("Good:")
    for l in spec.get("example_good","").splitlines():
        lines.append(f"  {l}")
    lines.append("")
    return "\n".join(lines)


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
