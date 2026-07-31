# Scrut

A lightweight, offline static review tool for the Python files you are about
to commit. Scrut looks at the working tree, picks out every changed `.py` file
that `git` knows about, parses each one with Python's `ast` module, and reports
structural issues against thresholds you can configure.

Zero dependencies. No network calls. No plugins. Just Python 3.10+, Git, and a
report printed to your terminal.

---

## Table of Contents

- [Why Scrut](#why-scrut)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Review rules](#review-rules)
- [Report format](#report-format)
- [Project layout](#project-layout)
- [Module reference](#module-reference)
- [Error handling](#error-handling)
- [Testing](#testing)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

---

## Why Scrut

Most review tools run over a whole codebase or require a server, a
configuration file, and a set of plugins before they are useful. Scrut takes
the opposite approach: it does exactly one thing, locally, in a fraction of a
second.

The tool is built around a simple observation — the code you should be worried
about is the code you just wrote. Scrut never scans your repository. It asks
Git what changed, filters for Python files, and reviews only those.

That makes it a natural fit for the moment just before `git push`: a fast,
terminal-only sanity check that a function didn't balloon, a file didn't get
unwieldy, or a signature didn't grow a fifth argument on the way to the
pull request.

## Why AST-based

Text patterns cannot reliably find a function definition that spans ten lines,
count nesting inside a comprehension, or tell a definition from a call. Python's
`ast` module turns source code into a syntax tree, which makes all of these
questions exact. Scrut walks that tree and measures:

- line spans via `end_lineno - lineno`
- parameter counts via `len(node.args.args)`
- nesting depth by recursing through `For`, `If`, and `While` nodes only

Because the analysis runs on a real parse tree, there are no regular-expression
edge cases. Every valid Python file is measured the same way.

---

## How it works

Scrut runs as a single, synchronous pipeline:

1. Load limits from `scrut.toml` (or use built-in defaults).
2. Verify the current directory is inside a Git work tree.
3. Run `git diff HEAD --name-only` to find files changed since the last commit.
4. Keep only existing files ending in `.py`.
5. For each file: read it, parse it, walk the tree, and check the five rules.
6. Print one aggregated report.

The pipeline is deliberately linear. There is no cache, no daemon, no remote
component — every invocation starts from scratch and finishes in milliseconds.

---

## Installation

Requirements: Python 3.10+ and Git 2.0+ on your `PATH`.

**From PyPI**

```bash
pip install scrut
```

**From source**

```bash
git clone https://github.com/mukundzha/scrut.git
cd scrut
pip install -e .
```

Both install a `scrut` console command backed by `scrut.cli:main`
(`pyproject.toml`).

---

## Usage

```bash
scrut
```

Run it from inside a Git repository. No arguments, no flags.

```
$ scrut
==================================================
SCRUT REPORT
==================================================

FILE
--------------------------------------------------
Name   : src/scrut/cli.py
Lines  : 274
Issues:
  [WARNING] File too large (274/50)

FUNCTIONS
--------------------------------------------------

Function 1: get_depth
Lines         : 11
Parameters    : 2
Nesting Depth : 2
Issues: None

CLASSES
--------------------------------------------------
No classes found.

==================================================
SUMMARY
==================================================
Functions Reviewed : 1
Classes Reviewed   : 0
Files Reviewed     : 1
Issues Found       : 1
==================================================
```

Three things to know about scope:

- Only files changed since `HEAD` are reviewed — staged and unstaged changes
  both count.
- The report covers every changed Python file, not just the first.
- Files that no longer exist on disk, and files that were never added to the
  index, are not part of the set. See [Limitations](#limitations).

---

## Configuration

Scrut reads `scrut.toml` from the current working directory. The file is
optional; without it, the built-in defaults apply.

```toml
[limits]
max_parameters    = 5
max_nesting       = 4
max_function_lines = 50
max_class_lines   = 200
max_file_lines    = 400
```

The `[limits]` table is merged over the defaults (`merge_limits` in
`src/scrut/config/loader.py`), so a partial file is valid — any key you omit
keeps its default value.

```toml
[limits]
max_parameters = 3
```

This is a complete configuration: every other limit falls back to the default
for that key. Note that `scrut.toml` is resolved relative to the directory you
run `scrut` from, so running the tool from a subdirectory means the file will
not be found and defaults are used.

### Default limits

| Key | Default | What it governs |
|---|---|---|
| `max_parameters` | 5 | Number of positional parameters a function may have |
| `max_nesting` | 4 | Depth of `for` / `if` / `while` blocks inside a function |
| `max_function_lines` | 50 | Length of a function, including its signature |
| `max_class_lines` | 200 | Length of a class, including methods |
| `max_file_lines` | 400 | Length of a whole file |

---

## Review rules

Every rule emits one `WARNING` issue when its threshold is exceeded. The message
always carries the measured value and the limit, e.g. `Too many parameters
(7/5)`.

| Rule | Condition | Message |
|---|---|---|
| Function length | `lines > max_function_lines` | `Function too long (N/limit)` |
| Parameter count | `params > max_parameters` | `Too many parameters (N/limit)` |
| Nesting depth | `depth > max_nesting` | `Nesting too deep (N/limit)` |
| Class length | `lines > max_class_lines` | `Class too large (N/limit)` |
| File length | `lines > max_file_lines` | `File too large (N/limit)` |

Nesting depth is counted by `get_depth()` in `src/scrut/cli.py`. Only `For`,
`If`, and `While` nodes increase the counter. `Try`, `With`, `AsyncFor`, and
`AsyncWith` blocks are deliberately excluded — the metric targets conditional
and loop complexity rather than general block structure.

---

## Report format

The report is assembled by `generate_report()` and printed to stdout. It has
four sections:

- **FILE** — one entry per reviewed file, with its line count and file-level
  issues.
- **FUNCTIONS** — one entry per function found in any reviewed file, showing
  lines, parameters, nesting depth, and function-level issues.
- **CLASSES** — one entry per class, with its line count and class-level
  issues, or `No classes found.` when there are none.
- **SUMMARY** — total counts for functions, classes, files, and issues.

The summary numbers are aggregated across every reviewed file.

---

## Project layout

```
scrut/
├── pyproject.toml           # Packaging, entry point, pytest config
├── scrut.toml               # This project's own limits
├── README.md
├── src/
│   └── scrut/
│       ├── __init__.py      # Package marker
│       ├── cli.py           # Git integration, analysis, reporting
│       └── config/
│           ├── __init__.py  # Package marker
│           ├── default.py   # DEFAULT_LIMITS
│           ├── loader.py    # scrut.toml reading and merging
│           └── validator.py # Reserved for future config validation
└── tests/
    └── test_git.py          # 12 unit tests
```

## Module reference

**`src/scrut/cli.py`** is the whole application. It contains:

- `is_gitrepo()` — runs `git rev-parse --is-inside-work-tree` and checks the
  exit code.
- `get_changed_files()` — runs `git diff HEAD --name-only` and returns the
  file list.
- `get_reviewable_files(files)` — filters to existing `.py` files.
- `read_file(file_path)` — reads a file, returning `None` instead of raising
  on `OSError`.
- `get_depth(node)` — recursive nesting-depth counter.
- `generate_report(...)` — prints the formatted report.
- `main()` — orchestrates everything and defines the per-file analysis
  (`analyze_file`), which parses the source, walks the AST, and applies the
  five rules.

**`src/scrut/config/default.py`** holds `DEFAULT_LIMITS`, the single source of
truth for fallback values.

**`src/scrut/config/loader.py`** implements `load_config()`, which reads
`scrut.toml` from the working directory and merges its `[limits]` table over
the defaults, and `merge_limits()`, which performs that merge.

**`src/scrut/config/validator.py`** exists as a placeholder for future
configuration validation. It is intentionally empty.

---

## Error handling

Scrut degrades gracefully on a per-file basis. A problem in one file never
stops the review of the others.

| Situation | Behaviour |
|---|---|
| Not inside a Git repository | Prints `Not inside a Git repository.` and exits |
| No changed Python files | Prints `No Python files to review.` and exits |
| A file cannot be read | An `[ERROR] Could not read file` entry is added; other files continue |
| A file fails to parse | An `[ERROR] Python syntax error` entry is added; other files continue |
| A limit is exceeded | A `[WARNING]` entry is added with the measured value and limit |

The tool always exits with status 0, whether or not issues were found. It is a
reporter, not a gatekeeper.

---

## Testing

```bash
pytest
```

The suite lives in `tests/test_git.py` and covers the Git helpers (repo
detection, changed-file parsing), file handling (filtering, reading, missing
files), the nesting-depth metric, configuration loading and merging, and an
end-to-end run of `main()` across three files — one clean, one over the limits,
one syntactically broken — asserting that all three are reported and the run
completes.

---

## Limitations

These are known constraints of the current implementation:

- **Untracked files are invisible.** `git diff` does not report files that have
  never been added to the index, so a brand-new `.py` file is skipped until it
  is staged.
- **Repositories with no commits.** `git diff HEAD` has nothing to compare
  against in a fresh repository, so the tool reports that there is nothing to
  review.
- **Configuration is resolved from the working directory only.** There is no
  upward search for `scrut.toml`, and no environment-variable or CLI override.
- **No exit-code signalling.** CI systems cannot currently fail a build on
  issues, because the exit status is always 0.
- **Parameter counting is positional-only.** `*args`, `**kwargs`, keyword-only
  parameters, and `self` are not part of `len(node.args.args)`, which under- or
  over-counts in some signatures.
- **Nested functions are treated as top-level.** An inner `def` is reported as
  its own function and adds to the enclosing function's nesting depth.
- **Plain-text output only.** There is no JSON or SARIF export for CI tooling.

---

## Contributing

The codebase is small on purpose. `cli.py` is the entire pipeline, the config
package is three short modules, and the test suite is one file.

Good places to start:

- Give `generate_report()` its own dedicated tests.
- Fill in `config/validator.py` so malformed `scrut.toml` values fail with a
  clear message instead of a traceback.
- Add an integration test that exercises `main()` inside a real temporary Git
  repository.

Run `pytest` before opening a pull request. The tests use `unittest.mock`,
`tmp_path`, and `monkeypatch`; no fixtures are shared across files.

---

## License

MIT. See `LICENSE`.
