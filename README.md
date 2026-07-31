# Scrut

Review the Python files you're about to commit — nothing else.

Scrut is a zero-dependency CLI that looks at your Git working tree, isolates
every changed `.py` file since the last commit, parses each one with Python's
own `ast` module, and reports structural problems against limits you can
configure. It runs offline, finishes in milliseconds, and answers one question
well: *is the code I just wrote still within the shape this project agrees on?*

---

## Why Scrut Exists

Code reviews catch what authors miss. But most review tooling either scans an
entire repository (slow, noisy, full of pre-existing debt) or requires a
configuration, a server, and a plugin ecosystem before it can say anything
useful.

Scrut starts from a different premise: the risk is in what changed. If a
function grew to 400 lines in this commit, that's new debt. If it was already
400 lines last week, that's a pre-existing problem — and it isn't what a
pre-push check should be shouting about.

That's why Scrut never scans. It asks Git what changed, filters for Python
files, and reviews only those. The result is a tool that fits in the quiet
moment before `git push`: fast enough to run every time, simple enough to
understand completely, and opinionated enough to be useful.

Regex-based linting can't reliably do this job. Multi-line signatures, nested
blocks, and definitions that look like calls defeat pattern matching. The
`ast` module parses source into a real syntax tree, which turns "how many
parameters does this function have" from a guessing game into arithmetic.

---

## Philosophy

The project is built on a few deliberate choices:

- **Small.** The entire pipeline is one module. You can read it in ten minutes.
- **Fast.** No cache, no daemon, no network. Every run starts from scratch and
  ends in milliseconds.
- **Predictable.** The same input always produces the same report. There is no
  state, no persistence, nothing hidden.
- **Git-first.** Git is the source of truth for what to review. No flag-driven
  file selection, no configuration files listing paths.
- **Honest failures.** One unreadable or syntactically broken file records an
  error and moves on. A broken file never silences the report for the others.
- **No unnecessary abstractions.** Five rules, three report shapes, one
  pipeline. When a rule is added, the AST walk gets a few lines, not a new
  framework.

---

## Architecture

```
┌────────────┐     ┌─────────────┐     ┌───────────────┐     ┌──────────┐
│   Git      │────▶│ Changed     │────▶│ .py filter    │────▶│ Loader   │
│ work tree  │     │ file list   │     │ + exists      │     │ scrut.toml│
└────────────┘     └─────────────┘     └───────────────┘     └────┬─────┘
                                                                  │ limits
                                                                  ▼
┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────┐
│ Report   │◀────│ Rule checks  │◀────│ AST walk      │◀────│ ast.parse│
│ generator│     │ 5 rules      │     │ functions/    │     │ + read   │
└──────────┘     └──────────────┘     │ classes       │     └──────────┘
                                      └───────────────┘
```

The pipeline is a straight line. Each stage narrows or transforms its input:

| Stage | Component | Responsibility |
|---|---|---|
| Discovery | `get_changed_files()` | `git diff HEAD --name-only` — every file modified since the last commit |
| Filtering | `get_reviewable_files()` | Keep existing `.py` files only |
| Limits | `load_config()` | Read `scrut.toml`, merge over `DEFAULT_LIMITS` |
| Analysis | `analyze_file()` | Read → `ast.parse` → walk → apply the five rules |
| Metrics | `get_depth()` | Recursive nesting counter (`For`, `If`, `While` only) |
| Reporting | `generate_report()` | Print the aggregated report and summary |

Failure handling lives at the file boundary: read and parse errors become
`ERROR` entries inside the report instead of exceptions that stop the run.

---

## Repository Structure

```
scrut/
├── pyproject.toml           # Packaging, entry point, pytest config
├── scrut.toml               # Limits used by this repository itself
├── README.md
├── src/
│   └── scrut/
│       ├── cli.py           # The entire pipeline: Git, analysis, report
│       └── config/
│           ├── default.py   # DEFAULT_LIMITS — single source of fallback truth
│           ├── loader.py    # scrut.toml reading + merging
│           └── validator.py # Reserved for future validation
└── tests/
    └── test_git.py          # 12 unit tests
```

The layout follows the src-layout convention required for clean packaging.
`cli.py` is the application; the `config` package isolates everything about
where limits come from, so the pipeline never has to know about TOML or
filesystem paths. `validator.py` is intentionally empty — a placeholder for
the day configuration values need type and range checking.

---

## How Scrut Works

When you run `scrut`, this happens in order:

1. **Load limits.** `load_config()` looks for `scrut.toml` in the current
   directory. If it exists, its `[limits]` table is merged over the defaults.
   If not, `DEFAULT_LIMITS` is used as-is.
2. **Check Git context.** `is_gitrepo()` runs `git rev-parse
   --is-inside-work-tree`. Outside a repository, Scrut prints
   `Not inside a Git repository.` and stops.
3. **Collect changed files.** `get_changed_files()` runs
   `git diff HEAD --name-only`. This covers both staged and unstaged changes
   against the last commit — exactly the set of files that will form the next
   push.
4. **Filter.** `get_reviewable_files()` keeps only files ending in `.py` that
   still exist on disk. If nothing qualifies, Scrut prints
   `No Python files to review.` and stops.
5. **Analyze each file.** For every candidate, `analyze_file()` reads the
   source, parses it with `ast.parse`, and walks the tree. Each `FunctionDef`
   is measured for length, parameters, and nesting depth; each `ClassDef` for
   length; the file itself for line count. Violations are collected as
   `WARNING` entries.
6. **Report.** `generate_report()` prints the FILE, FUNCTIONS, and CLASSES
   sections, followed by an aggregated SUMMARY.

The tool always exits with status 0 — it reports findings; it doesn't police
them.

---

## Installation

Requirements: **Python 3.10+** and **Git 2.0+** on your `PATH`. No other
dependencies exist or are installed.

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

Both paths register the `scrut` console script, which points at
`scrut.cli:main` in `pyproject.toml`.

---

## Quick Start

```bash
cd your-repo
# make a change
scrut
```

There are no arguments and no flags. If you changed Python files since the
last commit, you get a report. That's the entire interface.

---

## Configuration

Create a `scrut.toml` next to where you run `scrut`:

```toml
[limits]
max_parameters    = 5
max_nesting       = 4
max_function_lines = 50
max_class_lines   = 200
max_file_lines    = 400
```

Configuration is optional and partial by design. The `[limits]` table is
merged over `DEFAULT_LIMITS` (`merge_limits()` in `loader.py`), so omitting a
key means "use the default" — a file with just `max_parameters = 3` is a
complete, valid configuration.

| Key | Default | Meaning |
|---|---|---|
| `max_parameters` | 5 | Maximum positional parameters per function |
| `max_nesting` | 4 | Maximum `for`/`if`/`while` nesting depth inside a function |
| `max_function_lines` | 50 | Maximum function length, signature included |
| `max_class_lines` | 200 | Maximum class length, methods included |
| `max_file_lines` | 400 | Maximum file length |

One caveat: the file is resolved from the current working directory only.
Running `scrut` from a subdirectory means `scrut.toml` won't be found and
defaults apply.

---

## Rule Engine

Every rule emits one `WARNING` entry when its threshold is exceeded. Messages
always carry the measured value and the limit, so the report reads as a
self-contained explanation: `Function too long (87/50)` needs no context.

### Function length

A function that spans dozens of lines is hard to follow, hard to test, and
tends to accumulate responsibilities. This rule flags functions whose line
span — signature included — exceeds `max_function_lines`.

```python
def handle_request(payload):        # line 1
    ...                             # 87 lines of logic
```

```
[WARNING] Function too long (87/50)
```

### Parameter count

Every additional parameter multiplies the combinations a caller has to think
about. The rule counts `node.args.args` — positional and keyword parameters —
against `max_parameters`.

```python
def register_user(name, email, password, role, newsletter, locale, timezone):
```

```
[WARNING] Too many parameters (7/5)
```

### Nesting depth

Deep nesting is the cheapest way to build unreadable code. `get_depth()`
recurses through the tree and increments only on `For`, `If`, and `While`
nodes. `Try`, `With`, and async variants are deliberately excluded — the
metric targets conditional and loop complexity, not general block structure.

```python
def process(items):
    for item in items:
        if item.valid:
            while retry(item):
                ...
```

```
[WARNING] Nesting too deep (3/4)
```

### Class length

A class that outgrows `max_class_lines` has usually become a grab-bag of
state and behavior. The metric counts the full class span, methods included.

```
[WARNING] Class too large (240/200)
```

### File length

A 2,000-line module is hostile to navigation. The rule compares the parsed
line count against `max_file_lines`.

```
[WARNING] File too large (1200/400)
```

---

## Example Project

Consider a small library with three changed files:

```python
# utils.py
def normalize(text):
    return text.strip().lower()
```

```python
# api.py
class UserAPI:
    def create(self, name, email, password, role, notify, retries):
        if not name:
            raise ValueError("name required")
        ...
```

```python
# handlers.py
def main():
    try:
        api = UserAPI()
    except Exception:
        api = UserAPI(retries=5)
```

Run `scrut`:

- `utils.py` — clean. `normalize` has one parameter, no nesting, five lines.
- `api.py` — flagged. `create` has six parameters; `UserAPI` spans 48 lines,
  which is fine, but the parameter count exceeds the default limit of five.
- `handlers.py` — clean.

One warning, one file, zero noise from `utils.py` or any untouched module.

---

## Example Output

```
$ scrut
SCRUT REPORT
==================================================
==================================================

FILE
--------------------------------------------------
Name   : src/scrut/api.py
Lines  : 320
Issues:
  [WARNING] File too large (320/400)

FUNCTIONS
--------------------------------------------------

Function 1: create
Lines         : 41
Parameters    : 6
Nesting Depth : 3
Issues:
  [WARNING] Too many parameters (6/5)

CLASSES
--------------------------------------------------

Class: UserAPI
Lines: 48
Issues: None

==================================================
SUMMARY
==================================================
Functions Reviewed : 3
Classes Reviewed   : 1
Files Reviewed     : 3
Issues Found       : 2
==================================================
```

---

## Design Decisions

**Why AST and not regex?** Regex cannot count parentheses across lines,
measure nesting, or distinguish a definition from a call. The AST gives exact
answers for every valid Python file, including edge cases like comments
containing keywords and multi-line signatures.

**Why TOML?** It's the de facto standard for Python tool configuration, has a
zero-dependency parser in the standard library (`tomllib`), and reads clearly
in diffs. Configuration is a flat table of five numbers — anything heavier
would be overkill.

**Why `git diff HEAD` instead of `git diff`?** Plain `git diff` only covers
unstaged changes. Comparing against `HEAD` captures both staged and unstaged
work, which is the complete set of files that would land in the next push.

**Why only changed files?** Pre-existing issues are noise. A tool that reports
500 warnings on a 10-file commit buries the few issues that actually matter:
the ones the author just introduced.

**Why CLI-first?** The terminal is where the review happens — right before
commit and push. No daemon, no watch mode, no IDE plugin. One command, one
report, done.

---

## Performance

Runtime is bounded by what you touched, not what you own. Each changed file is
read, parsed once, and walked once. Parsing is linear in file size; the AST
walk and `get_depth()` recursion are linear in the number of nodes. There is
no caching because there is nothing to cache — the total work is a handful of
small files.

Two Git subprocess calls (`rev-parse`, `diff`) are the only external
dependency per run. On a typical commit, the tool finishes in well under 100
milliseconds.

---

## Contributing

The codebase is intentionally small, so contributing is approachable:

- Read `src/scrut/cli.py` — it is the entire pipeline.
- Run `pytest` before submitting; the suite lives in `tests/test_git.py`.
- Tests use `unittest.mock`, `tmp_path`, and `monkeypatch`. No shared
  fixtures, no plugins.

Good starting points:

- `generate_report()` deserves dedicated tests.
- `config/validator.py` is waiting for value validation so malformed
  `scrut.toml` values fail with a clear message instead of a traceback.
- A new rule is a few lines inside the AST walk in `analyze_file()`.

---

## Roadmap

- Validate `scrut.toml` values (types and ranges) before analysis
- Include untracked files and support repositories with no commits
- Add `--json` output and configurable exit codes for CI
- Count `*args`, `**kwargs`, and keyword-only parameters
- Search upward for `scrut.toml` from subdirectories
- Pre-commit hook support

---

## License

MIT. See `LICENSE`.
