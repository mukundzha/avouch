# scrut

A static review tool for the Python files you changed since the last commit.
Nothing else.

Scrut has zero dependencies. It asks Git what you modified, filters for
`.py` files, parses each with the standard `ast` module, and reports
structural problems against limits you configure in `scrut.toml`. It is
built for the seconds before `git push`: fast enough to run every time,
simple enough to read in ten minutes.

## Why it exists

Whole-repo linters are slow and noisy. Most of what they report is
pre-existing debt that predates your change, so the signal gets buried.
Scrut inverts that: the review set is exactly the files you are about to
commit, so every finding is something you introduced.

Regex linting cannot do this job. Counting parentheses across a multi-line
signature, measuring nesting, distinguishing a definition from a call —
pattern matching gives wrong answers to all three. The AST gives exact ones.

## How it works

One rule governs the design: the review set is computed, never configured.

1. `git diff HEAD --name-only` — every file modified since the last commit,
   staged or not. Plain `git diff` would silently skip staged files, so
   `HEAD` matters.
2. Keep files ending in `.py` that still exist on disk.
3. Parse each one and apply the five rules.
4. Print findings grouped per file.

Failure is contained per file. An unreadable or syntactically broken file
becomes an `ERROR` entry in the report and the run continues — a run over N
files always produces N file reports. The exit code is always 0. Scrut
reports; it doesn't gate.

## Features

- **Changed-file review only** — the review set comes from Git, never from
  configuration
- **Zero dependencies** — standard library only, Python 3.10+
- **Five structural rules** — function length, parameter count, nesting
  depth, class size, file size
- **Configurable limits** — optional `scrut.toml`, merged over defaults
- **Per-file error containment** — one broken file never cancels the review
  of the others
- **Terminal-aware output** — ANSI colors only on a TTY, plain text when
  piped

## Installation

Requires Python 3.10+ and Git on `PATH`.

```bash
pip install scrut
```

Or from source:

```bash
git clone https://github.com/mukundzha/scrut.git
cd scrut
pip install -e .
```

Both install the `scrut` console script (`scrut.cli:main`).

## Usage

```bash
cd your-repo
# make a change
scrut
```

No arguments, no flags. If you changed Python files since the last commit,
you get a report:

```
SCRUT [Review Summary]

2 file(s) need attention · 0 file(s) passed

src/scrut/report.py
  ⚠ render_report() — Function too long (53/50)
  ⚠ file — File too large (70/50)
tests/test_git.py
  ⚠ file — File too large (310/50)

✓ 0 compliant files hidden
```

`⚠` marks warnings, `✖` marks errors. Every message embeds the measured
value and the limit, so each line is self-explanatory.

Failure paths: outside a Git repository, it prints `Not inside a Git
repository.`; with no changed `.py` files, `No Python files to review.`;
when everything passes, `✓ All clean.`

## Rules

| Rule | Message | Default limit |
|---|---|---|
| Function length | `Function too long (N/limit)` | 50 |
| Parameter count | `Too many parameters (N/limit)` | 5 |
| Nesting depth | `Nesting too deep (N/limit)` | 4 |
| Class size | `Class too large (N/limit)` | 200 |
| File size | `File too large (N/limit)` | 400 |

### Nesting depth

`get_depth()` is a recursive maximum over the tree. A node adds a level
only when it is one of eight block types: `If`, `For`, `While`, `AsyncFor`,
`With`, `AsyncWith`, `Try`, `Match`. That enumeration is the entire
definition of the metric, and it is deliberate: comprehensions and lambdas
are data transformations, not control flow, so a 4-deep comprehension chain
does not count; sibling blocks do not stack — the metric is maximum depth,
not block count. Adding a block type is one line in `BLOCK_NODES`.

### Parameter count

Counts `node.args.args` — the parameters a caller sees in the signature.
`*args`, `**kwargs`, keyword-only parameters, and `self` are not counted.
The metric is a proxy for call-site complexity, not an inventory: a method
with `self` and two arguments is not a three-parameter design problem.

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

The `[limits]` table is merged over the defaults (`merge_limits()`), so a
file containing only `max_parameters = 3` is complete and valid. The
repository itself ships a stricter `scrut.toml` (`max_parameters = 4`,
`max_class_lines = 50`, `max_file_lines = 50`). The file is resolved from
the current working directory only.

## Architecture

The whole application is four modules plus a config package. `cli.py` is
orchestration and nothing else — every function it calls lives somewhere
else, and nothing imports `cli.py`. That downward dependency direction is
what makes the pipeline testable in isolation.

```
src/scrut/
├── cli.py          # entry point; wires the pipeline
├── git.py          # is_gitrepo, get_changed_files, get_reviewable_files
├── analyzer.py     # BLOCK_NODES, read_file, get_depth, analyze_file
├── report.py       # render_report, generate_report
└── config/
    ├── default.py  # DEFAULT_LIMITS
    └── loader.py   # load_config, merge_limits
```

`main()` loads limits, checks the repository, collects the review set, runs
`analyze_file(path, limits)` on each file, and hands the three flat report
lists to `render_report`. Analysis answers "what is true about this file?";
rendering answers "how do I show it?" — so functions and classes carry the
file they came from, and the renderer rebuilds the per-file grouping at
display time. Changing the output format touches `report.py` alone.

Errors are data, not exceptions. `read_file` returns `None` on `OSError`,
`ast.parse` failures are caught, and both become `ERROR` report entries.
The analyzer never raises.

## Development

```bash
python -m pytest tests/
```

The suite (`tests/test_git.py`, 22 tests) covers the git helpers, config
merging, all eight nesting block types, every analysis failure path, report
output, and an end-to-end run against a real temporary git repository —
git itself is not mocked. Mocking is limited to `subprocess.run` where a
real git isn't needed.

Adding a rule is a few lines inside the `analyze_file` walk plus a default
in `DEFAULT_LIMITS`. The renderer displays any `(severity, message)` pair
it receives, so reporting needs no changes.

## Known limitations

- Untracked files are invisible to `git diff HEAD` and never reviewed.
- A repository with no commits has nothing to diff against.
- `*args`, `**kwargs`, keyword-only parameters, and `self` are not counted.
- `AsyncFunctionDef` is not analyzed; async functions are skipped.
- A malformed `scrut.toml` raises instead of reporting a clean message.
- `scrut.toml` is looked up in the current directory only.
- Exit code is always 0, so CI needs a wrapper today.

## Roadmap

Informed by the limitations above: validate `scrut.toml` with readable
errors, review untracked files and commit-less repositories, count every
parameter kind, analyze `AsyncFunctionDef`, search upward for the config
file, and add `--json` output with configurable exit codes for CI.

## FAQ

**Why only changed files?** Pre-existing issues are noise. Reporting 500
warnings on a 10-file commit buries the few findings you introduced under
hundreds you didn't. The review set is the diff, so the output is always
relevant to the next push.

**Why AST instead of regex?** Regex cannot count parentheses across lines,
measure nesting, or distinguish a definition from a call. The AST answers
structural questions exactly for every valid Python file.

**Why always exit 0?** Scrut is a reviewer, not a gate. CI enforcement is
an explicit feature (see Roadmap), not the default behavior.

**Does it need a network or a daemon?** No. Two `git` subprocess calls and
the standard library. Runtime is bounded by the size of your diff, not your
repository.

## License

MIT — see `LICENSE`.
