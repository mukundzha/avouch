# avouch

**Review the Python you changed, not the Python you inherited.**

Avouch reviews only the `.py` files your next commit touches. It asks git
for that list, parses each file with `ast`, and reports structural problems
against limits you set in `avouch.toml`. No daemon, no network, nothing
else to install.

```bash
pip install avouch
cd your-repo
avouch init    # first run only: measure your code, write avouch.toml
avouch         # seconds before git push
```

---

## Why I built this

I was paying for an AI code reviewer that spent half its report on legacy
code I never wrote, and queued my actual diffs behind everyone else's. I
wanted a reviewer that only looks at the code I'm about to push, runs
locally in the seconds before `git push`, and costs nothing. So I built
one.

---

## Installation

Requires **Python 3.10+** (rules use `ast.Match`; configuration uses
`tomllib`) and **Git on `PATH`**.

```bash
pip install avouch
```

or from source:

```bash
git clone https://github.com/mukundzha/avouch.git
cd avouch
pip install -e .
```

---

## Quick start

Change a file, run it, read the report:

```text
$ avouch

AVOUCH · 2 FILES · 4 WARN
────────────────────────────────────────────────────────────────────────────────

bad.py:1: SCR002: Bare except detected. Catch a specific exception instead, e.g. except ValueError:.
  │
1 │ def connect(host, port, user, password, db, timeout):
  │     ^^^^^^^ SCR002
2 │     try:
  │

bad.py:1: SCR014: Too many parameters (6/5). Group related parameters into a data class or dictionary.
  │
1 │ def connect(host, port, user, password, db, timeout):
  │     ^^^^^^^ SCR014
2 │     try:
  │

────────────────────────────────────────────────────────────────────────────────
BY RULE

  SCR002 Bare except          1
  SCR014 Too many parameters  1

────────────────────────────────────────────────────────────────────────────────
PASSED
  ✓ src/util.py
```

Each finding is compiler-style: `file:line`, rule id and message, the
offending code with a caret under the flagged name, then a BY RULE tally
and a PASSING list for clean files. A clean run is one line:

```text
$ avouch

All clean.
```

Flags:

```bash
avouch            # human report
avouch --json     # one JSON document on stdout
avouch --docs     # built-in documentation; no review performed
avouch --changed  # compact added/deleted view of changed files vs HEAD
avouch --staged   # review only files staged for the next commit
avouch --all-files  # review every eligible Python file, not just the diff
avouch --not-git  # review every .py file on disk; no Git repo needed
avouch --quiet    # analyze, print no report; exit code only
avouch --verbose  # step-by-step review details on stderr
```

The review set is what git says is about to be pushed: files modified vs
`HEAD` plus untracked `.py` files. Generated files are skipped. Colors are
ANSI, only on a TTY; piped output is plain. Exit codes: `0` clean, `1`
findings, `2` couldn't run.

### First run: `avouch init`

Without `avouch.toml`, default limits apply — and legacy code may trip
them. `avouch init` measures your own repository (max parameters, nesting,
complexity, …) and writes an `avouch.toml` whose limits are that measured
reality plus one unit of headroom: the first run is clean by construction,
and anything *worse than your worst existing code* still gets flagged.

```text
$ avouch init
avouch.toml written: measured 12 maxima across 24 files

$ avouch
All clean.
```

`avouch init --dry-run` prints the would-be file without writing. Existing
`[rules]` and `ignore_paths` in your `avouch.toml` are preserved; rerunning
recomputes from scratch.

---

## Automation

`--json` prints a stable, versioned document on stdout — each violation
carries rule id, severity, message, file, component name, kind, and line;
`summary` holds the totals. Nothing leaks into it: no colors, no
timestamps. Exit codes behave exactly as in normal mode.

`--quiet` runs the same analysis and prints nothing; only the exit code
signals the outcome — made for hooks and scripts. Errors are never
silenced, and `--json` still emits its document.

---

## CI

Avouch is a plain console command with a documented exit code, so any CI
runner uses the same three steps: install, run, react to the exit code.

```yaml
name: Avouch

on:
  pull_request:
  push:

jobs:
  avouch:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Avouch
        run: python -m pip install avouch
      - name: Run Avouch
        run: avouch --all-files --json
```

A freshly checked-out tree has nothing changed vs `HEAD`, so the default
mode prints `error: nothing to review` — in CI use `--all-files` to review
the whole checkout. Findings make the step exit `1` and fail the job;
nothing is hidden with `|| true`. The repository itself ships
`.github/workflows/avouch.yml` and runs on its own.

---

## Configuration

Configuration is optional, partial, and declarative. Avouch looks for
`avouch.toml` in the current directory only — no upward search. Any subset
of keys merges over the built-in defaults; a missing file simply means
defaults.

```toml
[limits]        # numeric thresholds per rule
[rules]         # on/off toggle per rule
ignore_paths = ["tests", "migrations"]   # top-level: paths to skip
```

Change a threshold:

```toml
[limits]
max_parameters = 8    # allow up to 8 parameters instead of 5
```

Disable a rule:

```toml
[rules]
nested_function = false   # stop reporting SCR015
```

### Limits

| Key | Default | Meaning |
|-----|---------|---------|
| `max_parameters` | 5 | Max positional + keyword params |
| `max_nesting` | 5 | Max block nesting depth |
| `max_function_lines` | 300 | Max function line span |
| `max_class_lines` | 200 | Max class line span |
| `max_file_lines` | 1000 | Max file line count |
| `max_complexity` | 40 | Max cyclomatic complexity |
| `max_boolean_conditions` | 5 | Max operands in one chain |
| `max_if_chain` | 5 | Max if/elif links in a chain |
| `max_local_variables` | 30 | Max distinct assigned names |
| `max_return_statements` | 6 | Max `return`s per function |
| `max_lambda_nodes` | 10 | Max AST nodes in a lambda body |
| `max_large_comprehensions` | 40 | Max AST nodes in a comprehension |

Every rule also has a `[rules]` toggle of the same name (default `true`).
Each rule and its rationale is documented in `avouch --docs`.

### Ignoring paths

Exclude files with `avouch --ignore-path PATH` (repeatable) or
`ignore_paths` in `avouch.toml` (must be a list). Matching is
component-wise on repository-relative paths — `tests` skips `tests/` and
`tests/x.py` but not `tests.py`; a bare `"."` skips the whole repository.
CLI and TOML paths are combined and de-duplicated.

Malformed TOML, or a non-list `ignore_paths`, prints
`error: invalid avouch.toml configuration: ...` on stderr and exits `2`.
`avouch --verbose` shows which config was loaded; `avouch --docs` prints
the same limits and defaults for reference.

---

## How it works

```
cli.py ── git.py (find changed files) ── analyzer.py (read → ast.parse →
walk) ── rules/*.py (one analyze(node, limits) per rule) ── report.py
(terminal report / --json) [ ── utility/docs.py (--docs) ]
```

- `cli.py` only orchestrates; every function it calls lives in another
  module, and nothing imports `cli.py`.
- The review set comes from `git diff HEAD --name-only` plus untracked
  files; `--staged` uses `git diff --cached`, `--all-files` uses
  `git ls-files`, `--not-git` walks the disk.
- Findings are deduplicated per `(component, rule)` per file and checked
  against the rules before dispatch — disabled rules never run.
- `rich` is declared in `pyproject.toml` but never imported; rendering is
  hand-rolled ANSI in `report.py`.

Tests: `pip install -e . && python -m pytest tests/` — all fail-fast in a
fraction of a second, including an end-to-end run against a real temporary
git repository. The detailed v0.3.3 plan lives in
[`roadmap.md`](roadmap.md); the next release ships `avouch init`, a
findings baseline, parallel review, CI-native output formats, rule man
pages, a pre-commit hook, and inline diff annotations.

---

## FAQ

**Why only changed files?** Pre-existing issues are noise. A whole-repo run
buries the findings you introduced under hundreds you didn't — the review
set is the diff, so output is always relevant to the next push.

**Why `git diff HEAD` and not `git diff`?** Plain `git diff` covers only
unstaged changes; `HEAD` covers staged plus unstaged — the complete set of
files about to be pushed — and untracked files on top.

**Why AST instead of regex?** Regex cannot count parentheses across lines,
measure nesting, or distinguish a definition from a call. The AST answers
structural questions exactly for every valid Python file.

---

## Contributing

- **Tests before code.** A fix that cannot be expressed as a failing test
  first is not a fix yet.
- **Keep the diff small.** More than two modules touched needs a
  justification.
- **The standard-library runtime is the contract.** No new runtime
  dependencies without a written case.
- **The README is the spec.** If the behavior changed, the README changes
  in the same commit.

```bash
git clone https://github.com/mukundzha/avouch.git
cd avouch
pip install -e .
python -m pytest tests/
```

---

## License

MIT — see `LICENSE`.