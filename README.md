# avouch

**Review the Python you changed, not the Python you inherited.**

Avouch is a code reviewer for Python that only looks at the files your next commit touches. It asks `git` for that list, parses each changed `.py` with the standard `ast` module, and reports structural problems against limits you set in `avouch.toml`.

No daemon, no network, nothing to install alongside it. Run it seconds before `git push`:

```bash
pip install avouch
avouch
```

---

## Why

Paid AI reviewers wasted half their report on legacy I never wrote and queued my diffs behind everyone else's. I wanted a local, diff-only check that runs before `git push`, costs nothing, and shows only your changes — so I built Avouch.

- **Diff-only:** Review set is `git diff HEAD` + untracked, not whole repo.
- **Local:** Three `git` calls + `ast`, no server.
- **Yours:** Baseline hides legacy; every finding is attributable to your diff.

## Install

Requires **Python 3.10+** (`ast.Match`, `tomllib`) and `git` on `PATH`.

```bash
pip install avouch
```

or from source:

```bash
git clone https://github.com/mukundzha/avouch.git
cd avouch
pip install -e .
```

Both register `avouch` (`avouch.cli:main`).

## Quick start

Change a file, run it, read the compiler-style report:

```text
$ avouch
AVOUCH · 2 FILES · 4 WARN
────────────────────────────────────────────────
bad.py:1: SCR002: Bare except detected.
  │
1 │ def connect(host, port, ...):
  │     ^^^^^^^ SCR002
2 │     try:
BY RULE  SCR002 Bare except 1
         SCR014 Too many parameters 1
PASSED  ✓ src/util.py

$ avouch
All clean.
```

`file:line` + rule + message, dimmed context, caret under name, `BY RULE` tally, capped `PASSED` grid. Duplicate `(component, rule)` collapses per file.

Exit codes: `0` clean, `1` findings, `2` error. Colors only on TTY; piped is plain.

## Usage

Avouch takes no path argument — review set is Git-defined.

```bash
avouch --help        # all flags
avouch --docs        # full docs, no review (TTY browser or piped)
avouch --version     # avouch 0.3.3
```

### Review scopes (mutually exclusive)

**Default** — Changed vs `HEAD` + untracked. Best before `git push`.

Findings are limited to functions and classes whose source span overlaps an added or changed line. File-level findings still apply to the changed file. `--all-files` and `--not-git` review complete files.

**`--list-changed`** — Print each changed file path, one per line, and exit. Useful for scripts and tooling.
```bash
avouch --list-changed
# src/app.py
# tests/test_review.py
```

**`--display FILE`** — Display a file with syntax highlighting, line numbers, and an interactive pager. Press `q` to quit.
```bash
avouch --display src/avouch/cli.py
```

**`--changed`** — Diff view with `+`/`-` hunks and findings pinned inline. Local PR sketch.
```bash
avouch --changed
# [CHANGED FILES]
#   bad.py  +2 -1
#   ────────────────────
#     + def f(a,b,c,d,e,f):
#       ^ SCR014
```

**`--staged`** — Only staged (`git add`). Pre-commit uses this.
```bash
avouch --staged
```

**`--all-files`** — Every eligible `.py` via `git ls-files`. Use in CI where checkout is clean.
```bash
avouch --all-files
avouch --all-files --json
```

**`--not-git`** — Walk CWD for `.py` without Git. Skips `.venv`, `__pycache__`, `dist`, `build`, `node_modules`.
```bash
avouch --not-git
avouch --not-git --format github
```

Without a repo or on clean checkout:
```text
error: no Git repository found
hint: use --not-git
error: nothing to review
hint: nothing changed vs HEAD; use --all-files
```

### Output formats (mutually exclusive)

**Default** — Human report.

**`--json`** — Deterministic `{"version":1,"tool":"avouch","violations":[...],"summary":{...}}` with `rule`/`severity`/`message`/`file`/`name`/`kind`/`line` (`null` for file-level). Same exit codes, gate CI.
```bash
avouch --json | jq .summary.total
avouch --all-files --json > report.json
```

**`--format github`** — GitHub workflow commands for inline annotations.
```bash
avouch --all-files --format github
# ::warning file=bad.py,line=1,col=5,title=SCR014::Too many parameters...
# ::error for ERROR severity
```
Use in Actions to annotate PR diff.

**`--format sarif`** — SARIF 2.1.0 for code-scanning. Includes `tool.driver.rules` (20 rules) and `physicalLocation` spans.
```bash
avouch --all-files --format sarif > results.sarif
# upload with github/codeql-action/upload-sarif
```

`--json`/`--format` bypass `--quiet` and respect baseline filtering.

### Diagnostics

**`--quiet`** — Only exit code (errors still emit, `--json`/`--format` still emit).

**`--verbose`** — Step-by-step to stderr: `config: <resolved-path>`, `review set:`, `analyzing`, `suppressed`, `findings:`.

**`--fix`** — Apply safe fixes before reviewing. Currently replaces bare `except:` clauses with `except Exception:` and converts mutable literal/constructor defaults to `None` sentinel initialization. Combine with any review scope, including `--not-git`.

**`--ignore-path`** — Repeatable, component-wise (`tests` skips `tests/` not `tests.py`). Combined with `ignore_paths` in `avouch.toml`.

**`--select RULES`** — Review only the comma-separated rule IDs. Repeatable; `--ignore RULES` is applied afterward.

**`--ignore RULES`** — Skip the comma-separated rule IDs for this run without changing `avouch.toml`.

**`--docs`** — Full docs (`avouch --docs`) — workflow, 20 rules, limits, examples. Works outside repo.

## Init & Baseline

### `avouch init`

Measure repo maxima and write `avouch.toml` with `measured+1` headroom so first run is `All clean`. Rerun recomputes.

```bash
avouch init
avouch init --dry-run   # preview without writing
```

Example generated `avouch.toml`:

```toml
ignore_paths = ["tests"]
[limits]
max_parameters = 6
max_file_lines = 450
```

### `avouch baseline`

Snapshot current findings to `.avouch/baseline.json` (`rule+file+name+line` fingerprint; moving a function re-flags). Commit it. Next runs show only *new* findings.

```bash
avouch baseline          # snapshot full review
avouch                   # only new
avouch --no-baseline     # show all
avouch baseline          # idempotent, recomputes
```

`--verbose` shows `suppressed N finding(s) by baseline`, `BY RULE` shows `(+N suppressed)`. Malformed/wrong version → `error: invalid baseline:` exit 2. No file → no suppression. Composes with `init`.

### `avouch rule [ID]`

Per-rule help from single registry (same source as `--docs`).

```bash
avouch rule              # list all: SCR001  async function without await ...
avouch rule SCR002       # show one: name, description, scope, config, Bad/Good, severity
avouch rule SCR014       # too many parameters
```

Bare `avouch rule` lists 20 IDs; unknown → `error: unknown rule 'FOO'` exit 2; works outside repo.

## Configuration

`avouch.toml` is discovered by walking upward from `CWD` to filesystem root (so `tests/` uses repo root), optional/partial, merged over defaults. Malformed/invalid → `error: invalid avouch.toml configuration` exit 2.

```toml
[limits]        # thresholds per rule
[rules]         # on/off per rule (bool, default true)
ignore_paths = ["tests", "migrations"]
```

### Config file

- `avouch.toml` in upward-found directory, plain TOML; only `AVOUCH_FONT` env for terminal font.
- Missing/empty → silent defaults, no warning.

### Changing a threshold

```toml
[limits]
max_parameters = 8    # allow 8 instead of 5
max_file_lines = 2500
```

Only named keys change.

### Disabling a rule

```toml
[rules]
nested_function = false   # stop SCR015
```

One-line `[rules]` is valid.

### Rule toggles (all true)

| Key | Default | Rule |
|-----|---------|------|
| `async_without_await` | `true` | SCR001 |
| `bare_except` | `true` | SCR002 |
| `max_boolean_conditions` | `true` | SCR003 |
| `detect_duplicateb` | `true` | SCR004 |
| `max_large_comprehensions` | `true` | SCR005 |
| `empty_except` | `true` | SCR006 |
| `max_if_else_chain` | `true` | SCR007 |
| `max_lambda_nodes` | `true` | SCR008 |
| `max_local_variables` | `true` | SCR009 |
| `max_class_lines` | `true` | SCR010 |
| `max_file_lines` | `true` | SCR011 |
| `max_function_lines` | `true` | SCR012 |
| `max_nesting` | `true` | SCR013 |
| `max_parameters` | `true` | SCR014 |
| `nested_function` | `true` | SCR015 |
| `max_return_statements` | `true` | SCR016 |
| `mutable_default_args` | `true` | SCR017 |
| `max_complexity` | `true` | complexity |

### Limits (all tunable)

| Key | Default | Rule | Meaning |
|-----|---------|------|---------|
| `max_parameters` | 5 | SCR014 | Max params |
| `max_nesting` | 5 | SCR013 | Max depth |
| `max_function_lines` | 300 | SCR012 | Function span |
| `max_class_lines` | 200 | SCR010 | Class span |
| `max_file_lines` | 1000 | SCR011 | File lines |
| `max_complexity` | 40 | — | McCabe |
| `max_boolean_conditions` | 5 | SCR003 | Operands in chain |
| `max_if_chain` | 5 | SCR007 | If/elif length |
| `max_local_variables` | 30 | SCR009 | Assigned names |
| `max_return_statements` | 6 | SCR016 | Returns |
| `max_lambda_nodes` | 10 | SCR008 | Lambda nodes |
| `max_large_comprehensions` | 40 | SCR005 | Comprehension nodes |

Missing limit falls back to hardcoded default — partial never disables.

### Ignoring paths

Component-wise: `tests` skips `tests/` but not `tests.py`; `"."` skips repo.

- `avouch --ignore-path PATH` (repeatable) or `ignore_paths = ["tests"]` in `avouch.toml` (must be list).

Combined, de-duplicated, string-based (`is_ignored.py`), no FS access.

### Verifying & errors

`avouch --verbose` shows `config: <resolved-path>, N ignore path(s)` or `defaults (no avouch.toml)`.

- Malformed/invalid: `error: invalid avouch.toml configuration: limits.max_parameters must be a positive integer; got 'eight'` exit 2.
- Unknown keys silently ignored.
- `--ignore-path` appends; no flag for `[limits]`/`[rules]`; applies to all modes; severity fixed `WARNING`/`ERROR`.

### Example (this repo)

```toml
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
# ... all true
```

## GitHub Actions

Use `--all-files` in CI (fresh checkout has no diff):

```yaml
name: Avouch
on: [pull_request, push]
jobs:
  avouch:
    runs-on: ubuntu-latest
    permissions: {contents: read}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install avouch
      - run: avouch --all-files --format github  # annotations
      # or SARIF:
      # - run: avouch --all-files --format sarif > results.sarif
      # - uses: github/codeql-action/upload-sarif@v3
      #   with: {sarif_file: results.sarif}
```

`checkout` provides PR code; `avouch --all-files --format github` annotates diff; `permissions: contents: read` is enough. Pin `avouch==0.3.3`.

Why `--all-files`? Default is changed vs `HEAD` — fresh checkout is empty (`nothing to review`). `--changed`/`--staged` only make sense locally.

Exit codes `0` clean, `1` findings, `2` error — Actions fails non-zero, so `--all-files --format github` fails on findings. Fix or `ignore_paths`.

This repo ships `.github/workflows/avouch.yml` — enable in **Actions**, it does `pip install -e .` and runs `--all-files --format github` on PR.

## Pre-commit

Add to `pre-commit` so every commit reviews staged changes:

```yaml
repos: [{repo: https://github.com/mukundzha/avouch, rev: v0.3.2, hooks: [{id: avouch}]}]
# .pre-commit-hooks.yaml: entry avouch --staged, pass_filenames: false
```

Baselined findings don't fail the hook.

## Baseline

```bash
avouch baseline        # snapshot to .avouch/baseline.json
avouch                 # only new findings
avouch --no-baseline   # show all
```

Fingerprint `rule+file+name+line` (moving re-flags). Commit `.avouch/baseline.json`. `--verbose` shows suppressed count, `BY RULE` shows `(+N suppressed)`. Malformed → exit 2.

## Other CI

Any CI: `pip install avouch` → `avouch --all-files --json` → check exit code.

## Configuration

`avouch.toml` discovered by walking upward from CWD to FS root (so `tests/` uses root config), optional/partial, merged over defaults. Invalid `limits` (must be positive int), `rules` (bool), `ignore_paths` (list[str]) → `error: invalid avouch.toml configuration` exit 2.

```toml
[limits]
max_parameters = 8
[rules]
nested_function = false
ignore_paths = ["tests"]
```

Limits and toggles are all `true` by default; see `avouch --docs` for full table. `--ignore-path` appends to `ignore_paths`. No env vars.

## How it works

`cli.py` only orchestrates. Pipeline: `load_config` → `git` review set → `analyzer.analyze_file` (ast + walk cache + rules) → `baseline.filter` → `report` (or `--json`/`--changed`/`--quiet`). `--docs`/`--version` short-circuit.

See `avouch --docs` for mermaid diagrams and full pipeline.

## Layout

```
avouch.toml  .avouch/baseline.json
src/avouch/
  cli.py              # entry, only orchestrates
  baseline.py         # snapshot + suppression
  git.py              # review set
  analyzer.py         # ast walk, dispatch
  report.py           # terminal / json / github / sarif / diff
  rules/              # one analyze(node,limits) per rule
    complexity.py  max_nesting.py  max_parameters.py ...
  utility/
    walk.py  docs.py  is_generated.py  is_ignored.py  measure.py
  config/
    default.py  loader.py  # DEFAULT_LIMITS, load_config
tests/
  test_git.py         # 74 tests + real git repo
  test_init.py        # init/baseline
```

## Adding a rule

One file per rule with `analyze(node, limits) -> list[issue]`:

```python
{"rule": "SCR017", "severity": "WARNING",
 "message": "Description (value/limit). Remediation."}
```

Add toggle in `DEFAULT_RULES` (+limit in `DEFAULT_LIMITS` if needed), wire in `analyzer.py` with guard, add violation + boundary tests. Renderer handles any `(severity,message)`.

Example: `mutable_default_args` — flags `def f(x=[])`, suggests `None`.

## Testing

```bash
pip install -e . && python -m pytest
```

86 tests, <1s, no network. Covers git helpers, config validation (upward, `limits must be positive int`, `rules must be boolean`, `ignore_paths` list), nesting/complexity/boolean metrics, rule boundaries, unreadable/syntax errors, report/diff, `avouch rule`, `github`/`sarif` golden, `--docs` outside repo, real temp git repo. Only `subprocess.run` mocked.

## FAQ

**Changed files only?** Whole-repo buries your few findings under legacy noise; diff keeps it relevant to next push.

**Why `git diff HEAD` not `git diff`?** Plain `diff` is unstaged only; `HEAD` is staged+unstaged plus untracked — nothing missed.

**Why AST not regex?** Regex can't count cross-line parens, nesting, or def vs call; AST answers exactly.

**Exit codes?** `0` clean, `1` findings, `2` error. Reviews, doesn't gate — CI can still react.

**Network/daemon?** No — three `git` calls + stdlib; runtime ∝ diff, not repo.

**Baseline vs `ignore_paths`?** `ignore_paths` hides files forever; baseline hides *findings* at snapshot time but re-flags if moved — use baseline for legacy debt.

**`init` vs `baseline`?** `init` sets limits to `measured+1` so first run is `All clean`; `baseline` snapshots findings. Compose both for greenfield.

**`rule` vs `--docs`?** Same registry; `--docs` shows all, `avouch rule SCR002` shows one.

## License

MIT — see `LICENSE`.
