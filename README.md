# Scrut

**scrut** is a static analysis tool that reviews unstaged Python changes before they reach a pull request. It works entirely offline, depends only on the standard library, and runs in under a second.

It checks four structural rules — function parameters, nesting depth, file size, and class size — by parsing your changed files with Python's AST module.

---

## Features

- Detects whether you are inside a Git repository
- Collects unstaged changed files via `git diff --name-only`
- Filters to `.py` files and validates they exist before analysis
- Parses source code with Python's built-in `ast` module
- Flags functions with excessive parameters (default >5)
- Measures `for`/`if`/`while` nesting depth inside functions (default >4)
- Flags files exceeding 400 lines and classes exceeding 200 lines
- Prints a formatted report to stdout

---

## Architecture

Scrut runs as a single synchronous pipeline. No caching, no async, no external services.

```
Git repository
     |
     v
is_gitrepo()          — exits if the working directory is not inside a Git work tree
     |
     v
get_changed_files()   — runs git diff --name-only
     |
     v
get_reviewable_files() — filters changed files to .py, checks they exist
     |
     v
read_file()           — reads the first changed Python file
     |
     v
ast.parse()           — parses source into an AST
     |
     v
ast.walk()            — iterates FunctionDef and ClassDef nodes
     |
     v
Rule checks           — parameter count, nesting depth, file/class line limits
     |
     v
generate_report()     — prints the formatted report to stdout
```

Every invocation starts from scratch. There is no incremental or cached analysis.

The data model for reports is a list of dictionaries:

```python
# Function report
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
# File and class reports
{
    "name": "src/handler.py",
    "lines": 450,
    "issues": [
        {"severity": "WARNING", "message": "File too large (450/400)"}
    ]
}
```

---

## Project structure

```
scrut/
├── pyproject.toml        # packaging, metadata, pytest config
├── LICENSE
├── README.md
├── .gitignore
├── src/
│   └── scrut/
│       ├── __init__.py   # package marker (empty)
│       └── cli.py        # all analysis logic (233 lines)
└── tests/
    └── test_git.py       # 7 unit tests (113 lines)
```

The only source file is `src/scrut/cli.py`. It contains the full pipeline — Git detection, file filtering, AST parsing, rule checking, and report generation — in a single module.

The test file is named `test_git.py` for historical reasons. It imports from `scrut.cli`.

---

## Installation

Requires **Python 3.10 or later** and **Git 2.0+**. No other dependencies.

```bash
git clone https://github.com/mukundzha/scrut.git
cd scrut
python -m venv venv
source venv/bin/activate
pip install -e .
```

The `pyproject.toml` registers a CLI entry point during installation:

```toml
[project.scripts]
scrut = "scrut.cli:main"
```

After install, the `scrut` command is available on your PATH.

---

## Usage

```bash
scrut
```

Or without installing:

```bash
PYTHONPATH=src python -m scrut.cli
```

### What the tool does

1. Verifies the current directory is inside a Git repository
2. Runs `git diff --name-only` to find unstaged changed files
3. Filters the list to only `.py` files that exist on disk
4. Reads the **first** `.py` file from the filtered list
5. Parses it with `ast.parse`
6. Walks the AST looking for `FunctionDef` and `ClassDef` nodes
7. Checks each node against four rules
8. Prints the report to stdout

### Exit code

The tool always exits with code 0, regardless of issues found.

---

## Example output

Running against a file that triggers all four rules:

```
==================================================
SCRUT REPORT
==================================================

FILE
--------------------------------------------------
Name   : src/handler.py
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

Error messages:

| Scenario | Output |
|---|---|
| Not in a Git repo | `Not inside a Git repository.` |
| No changed Python files | `No Python files to review.` |
| Python syntax error | `Python syntax error.` |
| File not readable | `Couldn't read <path>` |

---

## Review rules

All thresholds are module-level constants in `src/scrut/cli.py`:

```python
PARAMETER_LIMIT = 5
NESTING_LIMIT = 4
FILE_LINE_LIMIT = 400
CLASS_LINE_LIMIT = 200
```

| Rule | Threshold | Severity | Description |
|---|---|---|---|
| Maximum parameters | >5 | WARNING | Function has more arguments than allowed |
| Maximum nesting | >4 | WARNING | `for`/`if`/`while` blocks nested deeper than 4 levels inside a function |
| Maximum file size | >400 lines | WARNING | Source file exceeds the line count limit |
| Maximum class size | >200 lines | WARNING | Class definition exceeds the line count limit |

All issues carry `WARNING` severity. There is no `ERROR` level.

### Nesting depth

`get_depth()` walks child AST nodes and counts depth only for `ast.For`, `ast.If`, and `ast.While` nodes. This targets logical complexity — `with`, `try`, and `async for` do not increase the counter.

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

---

## Testing

Tests use **pytest** with `unittest.mock` for subprocess isolation.

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
```

### What each test covers

| Test | What it validates |
|---|---|
| `test_get_reviewable_files` | Only `.py` files that exist on disk pass the filter |
| `test_get_depth_no_nesting` | A flat function returns depth 0 |
| `test_get_depth_nested` | `if > while > for` returns depth 3 |
| `test_read_file` | Reads file contents correctly using `tmp_path` |
| `test_get_changed_files` | Mocks `subprocess.run`, verifies stdout is parsed into a list |
| `test_is_gitrepo_true` | Returns `True` when `git rev-parse` exits with code 0 |
| `test_is_gitrepo_false` | Returns `False` when `git rev-parse` exits with code 1 |

Tests use `tmp_path` (a pytest built-in fixture) for filesystem operations and `unittest.mock.patch` for subprocess isolation. `get_reviewable_files` now creates real files via `tmp_path.write_text()` and checks for existence — a change from the earlier version that only filtered by extension.

pytest configuration:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

The `pythonpath` setting adds `src/` to `sys.path` so `from scrut.cli import ...` resolves during test collection.

---

## Current limitations

- **Single-file review**: Only the first changed Python file is analyzed (`reviewable_files[0]` in `main()`). The data structures support multiple files but the loop does not iterate.
- **Unstaged changes only**: `git diff --name-only` does not return staged files. Files added with `git add` are invisible to Scrut.
- **No exit code signaling**: The tool exits 0 regardless of whether issues are found.
- **No configuration**: Thresholds are hardcoded. No config file, environment variables, or CLI flags.
- **Plain text output only**: No JSON, SARIF, or other machine-readable formats.
- **No rule plugin system**: Adding a new rule means editing `cli.py` directly.

---

## Roadmap

- Review all changed files instead of only the first one
- Support staged files (`git diff --cached`)
- Add JSON output for CI integration
- Make rules configurable via `pyproject.toml` or a config file
- Expand rule set (unused imports, bare except clauses, missing docstrings)
- Add pre-commit hook support

---

## Contributing

The codebase is a single 233-line module and one 113-line test file. Good starting points:

- `generate_report()` has no dedicated test
- Multi-file iteration in `main()` is the most requested fix
- A new rule can be added by extending the AST walk loop in `main()`

Run `pytest` before submitting changes.

---

## License

MIT. See `LICENSE`.
