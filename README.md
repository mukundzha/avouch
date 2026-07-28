# Scrut

Local static analysis for unstaged Python changes. Runs against `git diff` output, parses changed files with Python's AST, and flags common structural issues before they reach a pull request.

The tool is in early development. It currently reviews one file per run and checks four structural rules. There is no plugin system, no configuration file, and no CI integration yet.

---

## Features

### Repository detection

Detects whether the current working directory is inside a Git repository by running `git rev-parse --is-inside-work-tree`. If not, it exits immediately.

### Changed file collection

Runs `git diff --name-only` to collect unstaged changed files.

### Python file filtering

Filters the changed file list to only `.py` files.

### Static analysis via AST

Parses the first changed Python file using Python's built-in `ast` module, then walks the tree looking for `FunctionDef` and `ClassDef` nodes. Four rules are checked:

- **Function parameter count** — flags functions with more parameters than the configured limit
- **Nesting depth** — measures how deeply `for` / `if` / `while` blocks are nested inside each function
- **File size** — flags files exceeding the line limit
- **Class size** — flags classes exceeding the line limit

### Report generation

Prints a formatted summary to stdout showing each function, class, and file with any issues found. All issues currently carry `WARNING` severity. No machine-readable output format exists yet.

---

## Architecture

Scrut operates as a single-pass pipeline with no persistence, caching, or external communication.

```
Git repository
      |
      v
  is_gitrepo()          ---- exits if not a Git repo
      |
      v
  get_changed_files()   ---- git diff --name-only
      |
      v
  get_reviewable_files() -- filters to .py files, exits if none
      |
      v
  read_file()           ---- reads the first changed file
      |
      v
  ast.parse()           ---- parses source into AST
      |
      v
  ast.walk()            ---- iterates FunctionDef + ClassDef nodes
      |
      v
  Rule checks           ---- parameter count, nesting depth, line counts
      |
      v
  generate_report()     ---- prints results to stdout
```

The pipeline is fully synchronous. There is no async I/O, no worker pool, and no incremental analysis. Every invocation starts from scratch.

Data model for reports is a list of dictionaries:

```python
# Function report structure
{
    "name": "process_data",
    "lines": 34,
    "parameters": 8,
    "nesting_depth": 5,
    "issues": [
        {"severity": "WARNING", "message": "Too many parameters (8/5)"},
        {"severity": "WARNING", "message": "Nesting too deep (5/4)"}
    ]
}
```

```python
# File and class reports follow the same pattern
{
    "name": "src/handler.py",
    "lines": 450,
    "issues": [
        {"severity": "WARNING", "message": "File too large (450/400)"}
    ]
}
```

All logic lives in a single module (`git.py`). The `review.py` module exists as a placeholder but contains no code yet.

---

## Project structure

```
scrut/
├── pyproject.toml          # pytest configuration only
├── LICENSE                 # MIT
├── README.md
├── .gitignore
└── scrut/
    └── src/
        └── scrut/
            ├── __init__.py     # empty package marker
            ├── git.py          # all analysis logic (229 lines)
            └── review.py       # placeholder for future rule engine
└── tests/
    └── test_git.py             # 7 unit tests (101 lines)
```

The `scrut/src/scrut` nesting is three levels deep because the project uses an `src`-layout. This keeps the package directory separate from the project root and is the recommended layout for Python packaging. The `pyproject.toml` adds `scrut/src` to the Python path for pytest so imports like `from scrut.git import ...` work in tests.

Two files are empty placeholders:

- **`__init__.py`** — makes the directory a Python package, currently unused
- **`review.py`** — intended for a future rule engine abstraction

---

## Installation

Requires Python 3.10 or later. No external dependencies.

```bash
git clone https://github.com/mukundzha/scrut.git
cd scrut
python -m venv venv
source venv/bin/activate
pip install -e .
```

The `-e` flag installs in editable mode so changes to the source files are reflected immediately.

---

## Usage

Run from inside any Git repository with unstaged changes:

```bash
python -m scrut.src.scrut.git
```

There is no CLI entry point registered in `pyproject.toml`. The tool is invoked via Python module execution. This will be replaced with a proper `scrut` command once the tool matures.

### What happens

1. Checks that you are in a Git repository
2. Collects unstaged changed files via `git diff --name-only`
3. Filters to `.py` files
4. Reads the **first** `.py` file from the list
5. Parses it with `ast.parse`
6. Walks the AST for functions and classes
7. Checks rules and collects issues
8. Prints the report

If no issues are found, the report still shows every function and class with "Issues: None".

### Exit behavior

The tool exits with code 0 in all cases — even when issues are found, when not in a Git repo, or when a syntax error is encountered. There is currently no mechanism to fail based on issue count.

---

## Example output

Running against a file with violations:

```
==================================================
SCRUT REPORT
==================================================

FILE
--------------------------------------------------
Name   : src/legacy_handler.py
Lines  : 500
Issues:
  [WARNING] File too large (500/400)

FUNCTIONS
--------------------------------------------------

Function 1: process_user_data
Lines         : 45
Parameters    : 12
Nesting Depth : 6
Issues:
  [WARNING] Too many parameters (12/5)
  [WARNING] Nesting too deep (6/4)

Function 2: normalize_email
Lines         : 8
Parameters    : 1
Nesting Depth : 0
Issues: None

CLASSES
--------------------------------------------------
No classes found.

==================================================
SUMMARY
==================================================
Functions Reviewed : 2
Classes Reviewed   : 0
Files Reviewed     : 1
Issues Found       : 3
==================================================
```

If no changed Python files exist:

```
No Python files to review.
```

If not in a Git repository:

```
Not inside a Git repository.
```

---

## Review rules

All thresholds are defined as module-level constants in `scrut/src/scrut/git.py`:

```python
PARAMETER_LIMIT = 5
NESTING_LIMIT = 4
FILE_LINE_LIMIT = 400
CLASS_LINE_LIMIT = 200
```

| Rule | Threshold | Severity | Description |
|---|---|---|---|
| Maximum parameters | >5 | WARNING | Function accepts more parameters than the limit |
| Maximum nesting | >4 | WARNING | Control flow (for/if/while) is nested beyond 4 levels deep inside a function |
| Maximum file size | >400 lines | WARNING | File exceeds the line limit |
| Maximum class size | >200 lines | WARNING | Class exceeds the line limit |

### Nesting depth measurement

The `get_depth()` function recursively walks child AST nodes and counts depth only for `ast.For`, `ast.If`, and `ast.While` nodes. Other constructs like `with`, `try`, and `async for` do not increase nesting depth. This is intentional — the rule targets logical complexity from conditional and loop nesting, not structural Python constructs.

```python
def get_depth(node, depth=0):
    max_depth = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.For, ast.If, ast.While)):
            max_depth = max(max_depth, get_depth(child, depth + 1))
        else:
            max_depth = max(max_depth, get_depth(child, depth))
    return max_depth
```

### Severity

All issues are assigned `WARNING` severity. There is no `ERROR` level and no configuration to promote warnings to errors. This is a known limitation.

---

## Testing

Uses pytest with `unittest.mock` for subprocess isolation.

```bash
pytest
```

Or with verbose output:

```bash
pytest -v
```

Expected output:

```
tests/test_git.py::test_get_reviewable_files PASSED
tests/test_git.py::test_get_depth_no_nesting PASSED
tests/test_git.py::test_get_depth_nested PASSED
tests/test_git.py::test_read_file PASSED
tests/test_git.py::test_get_changed_files PASSED
tests/test_git.py::test_is_gitrepo_true PASSED
tests/test_git.py::test_is_gitrepo_false PASSED

======= 7 passed in 0.12s =======
```

### Test coverage

| Test | What it covers |
|---|---|
| `test_get_reviewable_files` | Only `.py` files pass the filter, others excluded |
| `test_get_depth_no_nesting` | Flat function returns depth 0 |
| `test_get_depth_nested` | `if > while > for` returns depth 3 |
| `test_read_file` | File contents read correctly with `tmp_path` |
| `test_get_changed_files` | `subprocess.run` mocked, stdout parsed into list |
| `test_is_gitrepo_true` | Git detection returns `True` for return code 0 |
| `test_is_gitrepo_false` | Git detection returns `False` for return code 1 |

Tests use `tmp_path` (pytest built-in fixture) for filesystem operations and `unittest.mock.patch` for subprocess calls. There is no integration test that runs against a real Git repository.

pytest configuration lives in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["scrut/src"]
testpaths = ["tests"]
```

The `pythonpath` setting ensures `from scrut.git import ...` resolves correctly.

---

## Current limitations

These are known gaps in the current implementation:

### Single-file review

Only the first changed Python file is analyzed (`reviewable_files[0]` on line 146 of `git.py`). If 15 files were changed, only one is reviewed. The report data structures support multiple files (they are lists), but the `main()` function never iterates beyond index 0.

### Unstaged changes only

`git diff --name-only` returns unstaged changes. Staged but uncommitted changes are not included. This means if you `git add` a file before running Scrut, it will not be reviewed.

### No CLI entry point

The tool runs via `python -m scrut.src.scrut.git`. There is no `scrut` command installed in the PATH.

### No configuration

All thresholds are hardcoded. There is no config file, no environment variable support, and no command-line flags.

### No formatting options

Output is plain text to stdout. No JSON, no SARIF, no machine-readable formats. Exit code is always 0 regardless of issues found.

### No plugin system

Rules are hardcoded in the AST walk loop. Adding a new rule requires editing `git.py` directly.

---

## Roadmap

These items are planned but not yet implemented:

- Iterate over all changed files, not just the first one
- Add support for staged files (`git diff --cached`)
- Register a proper `scrut` CLI entry point via `pyproject.toml`
- Add JSON output format for CI integration
- Make rules configurable via a file or environment variables
- Expand rule set (unused imports, bare except clauses, missing docstrings)
- Extract rule engine into `review.py`
- Add pre-commit hook support
- Support for non-Python file types

---

## Contributing

The codebase is small — two source files, one test file, under 350 lines total. A good starting point is reviewing the `main()` function in `git.py` and identifying what to extract next.

Potential contribution areas:

- Add a test for the `generate_report()` function (currently untested)
- Implement multi-file iteration in `main()`
- Add a new rule and its corresponding test
- Introduce the rule engine abstraction in `review.py`

The project uses standard pytest with `unittest.mock`. Run `pytest` before submitting changes.

---

## License

MIT. See `LICENSE` for the full text.
