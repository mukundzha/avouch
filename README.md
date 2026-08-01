# scrut

A review tool for the Python files you changed since the last commit. Nothing
else.

Scrut walks your Git worktree (`git diff HEAD --name-only`), keeps the `.py`
files, parses each one with the standard `ast` module, and reports structural
problems against limits you set in `scrut.toml`. It has zero dependencies, no
daemon, no network access, and it runs in milliseconds. Run it before `git
push`.

## How it decides what to review

The review set is computed, not configured:

1. `git diff HEAD --name-only` — every file modified since the last commit,
   staged or not. `HEAD` matters: plain `git diff` would silently skip staged
   files.
2. Filter to files ending in `.py` that still exist on disk.
3. If nothing qualifies, the tool says so and exits.

Whole-repo linters report pre-existing debt. Scrut only reports what this
commit introduced, which is what a pre-push check should be telling you.

## Installation

- Python 3.10+ (the AST rules use `ast.Match` and config uses `tomllib`)
- Git on `PATH`

```bash
pip install scrut
```

or from source:

```bash
pip install -e .
```

This installs the `scrut` console script (`scrut.cli:main` in
`pyproject.toml`).

## Usage

```bash
scrut
```

No arguments, no flags. Output is grouped per file, with warnings and errors
inline:

```
SCRUT  [Review Summary]

3 files need attention · 2 files passed

main.py
  ⚠ create_needs_review_content() — Function too long (55/50)
  ⚠ file — File too large (144/50)

src/scrut/analyzer.py
  ⚠ analyze_file() — Function too long (114/50)
  ⚠ file — File too large (150/50)

✓ 2 compliant files hidden
```

Colors are ANSI and are only emitted when stdout is a TTY; piped output is
plain. `⚠` marks warnings, `✖` marks errors.

Exit status is always 0. Scrut reports findings; it doesn't gate anything.

### Failure paths

- Not inside a Git repository → `Not inside a Git repository.`
- No changed `.py` files → `No Python files to review.`
- Unreadable or syntactically broken file → recorded as an `ERROR` entry in
  the report; remaining files are still analyzed.

## Rules

All findings are `WARNING` (or `ERROR` for file-level failures) and always
include measured value and limit, so each line is self-explanatory.

| Rule | Message | Default limit |
|---|---|---|
| Function length | `Function too long (N/limit)` | 50 |
| Parameter count | `Too many parameters (N/limit)` | 5 |
| Nesting depth | `Nesting too deep (N/limit)` | 4 |
| Class size | `Class too large (N/limit)` | 200 |
| File size | `File too large (N/limit)` | 400 |

### Nesting depth

`get_depth()` recurses the AST and counts a node as one level when it is one
of:

```python
ast.If, ast.For, ast.While, ast.AsyncFor, ast.With,
ast.AsyncWith, ast.Try, ast.Match
```

Comprehensions, lambdas, and nested `def` statements do not add depth. Sibling
blocks don't stack — the metric is maximum depth, not block count.

### Parameter count

Counts `node.args.args` only: positional and keyword arguments. `*args`,
`**kwargs`, keyword-only parameters, and `self` are not counted (see
Limitations).

## Configuration

Optional `scrut.toml` in the directory you run from:

```toml
[limits]
max_parameters    = 5
max_nesting       = 4
max_function_lines = 50
max_class_lines   = 200
max_file_lines    = 400
```

The `[limits]` table is merged over the defaults (`merge_limits()` in
`config/loader.py`), so a file containing only `max_parameters = 3` is
complete and valid. The repository itself ships a stricter `scrut.toml`
(`max_parameters = 4`, `max_class_lines = 50`, `max_file_lines = 50`).

The file is resolved from the current working directory only.

## Architecture

```
src/scrut/
├── cli.py          # entry point; orchestration only
├── git.py          # is_gitrepo, get_changed_files, get_reviewable_files
├── analyzer.py     # BLOCK_NODES, read_file, get_depth, analyze_file
├── report.py       # render_report, generate_report
└── config/
    ├── default.py  # DEFAULT_LIMITS
    └── loader.py   # load_config, merge_limits
```

One module per responsibility, each testable in isolation. `cli.py` contains
no logic beyond wiring: every function it calls lives in `git.py`,
`analyzer.py`, or `report.py`.

Pipeline:

1. `load_config()` — read `scrut.toml`, merge over defaults.
2. `is_gitrepo()` / `get_changed_files()` / `get_reviewable_files()` — turn
   the worktree into a list of changed `.py` files.
3. `analyze_file(file_path, limits)` — read (utf-8), `ast.parse`, walk the
   tree, apply the five rules. Returns `(functions, files, classes)`; each
   function and class report carries the source file it came from.
4. `render_report()` — group findings per file, print.

Errors are contained at the file boundary: unreadable and unparsable files
become `ERROR` entries instead of aborting the run.

## Development

```bash
python -m pytest tests/
```

The suite (`tests/test_git.py`, 22 tests) covers the git helpers, config
merging, all eight block node types for nesting depth, every analysis
failure path, report output, and a full end-to-end run against a real
temporary git repository. Mocking is limited to `subprocess.run` where a real
git isn't needed.

## Known limitations

- Untracked files are invisible to `git diff HEAD` and never reviewed.
- A repository with no commits has nothing to diff against.
- `*args`, `**kwargs`, keyword-only parameters, and `self` are not counted.
- `AsyncFunctionDef` is not analyzed; async functions are skipped.
- A malformed `scrut.toml` (bad TOML or wrong value types) raises instead of
  reporting a clean message.
- `scrut.toml` is looked up in the current directory only.
- Exit code is always 0, so the tool can't gate CI without a wrapper.

## License

MIT — see `LICENSE`.
