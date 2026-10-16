# avouch

**Review the Python you changed, not the Python you inherited.**

Avouch is a code reviewer for Python that only looks at the files your next commit touches. It asks `git` for that list, parses each changed `.py` with the standard `ast` module, and reports structural problems against limits you set in `avouch.toml`.

No daemon, no network, nothing to install alongside it. Run it seconds before `git push`:

```bash
pip install avouch
avouch
```

- **Diff-only** — review set is `git diff HEAD` + untracked, not the whole repo.
- **Local** — three `git` calls + `ast`, no server.
- **Yours** — baseline hides legacy; every finding is attributable to your diff.

Exit codes: `0` clean, `1` findings, `2` error. Colors only on TTY; piped output is plain.

---

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

## Quick start

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

---

## Usage

Avouch takes no path argument — the review set is Git-defined. Full details live in `avouch --docs`.

### Review scopes (mutually exclusive)

| Flag | Scope |
|------|-------|
| *(default)* | Changed vs `HEAD` + untracked. Best before `git push`. |
| `--staged` | Only staged (`git add`). Used by pre-commit. |
| `--changed` | Diff view with `+`/`-` hunks and findings pinned inline. |
| `--all-files` | Every eligible `.py` via `git ls-files`. Use in CI. |
| `--not-git` | Walk CWD for `.py` without Git (skips `.venv`, `__pycache__`, `dist`, `build`, `node_modules`). |
| `--list-changed` | Print each changed file path, one per line, and exit. |
| `--display FILE` | Syntax-highlighted file with line numbers and an interactive pager (`q` quits). |

Default scope limits findings to functions and classes whose source span overlaps an added or changed line; file-level findings still apply to the changed file.

```bash
avouch --list-changed
# src/app.py
# tests/test_review.py

avouch --changed
# [CHANGED FILES]
#   bad.py  +2 -1
#   ────────────────────
#     + def f(a,b,c,d,e,f):
#       ^ SCR014
```

Without a repo, or on a clean checkout:

```text
error: no Git repository found
hint: use --not-git
error: nothing to review
hint: nothing changed vs HEAD; use --all-files
```

### Output formats (mutually exclusive)

| Flag | Output |
|------|--------|
| *(default)* | Human report. |
| `--json` | `{"version":1,"tool":"avouch","violations":[…],"summary":{…}}` with `rule`/`severity`/`message`/`file`/`name`/`kind`/`line` (`null` for file-level). Same exit codes, gates CI. |
| `--format github` | Workflow commands for inline annotations: `::warning file=bad.py,line=1,…`. |
| `--format sarif` | SARIF 2.1.0 with `tool.driver.rules` (20 rules) and `physicalLocation` spans, for code-scanning. |

`--json`/`--format` bypass `--quiet` and respect baseline filtering.

### Diagnostics

| Flag | Effect |
|------|--------|
| `--quiet` | Only exit code (errors and `--json`/`--format` still emit). |
| `--verbose` | Step-by-step to stderr: `config:`, `review set:`, `analyzing`, `suppressed`, `findings:`. |
| `--fix` | Apply safe fixes before reviewing — `except:` → `except Exception:`, mutable defaults → `None` sentinel, `async def` without `await` → `def`, `shell=True` → `shell=False`. `--fix-dry-run` previews. |
| `--watch` | Watch reviewable Python files plus `avouch.toml` and `.avouch/baseline.json`, re-running on change (`0.5s` poll, `AVOUCH_WATCH_INTERVAL`; `Ctrl+C` quits). Clears screen on TTY. Not compatible with `--json` / `--format` / `--list-changed` / `--display`. |
| `--ignore-path PATH` | Repeatable, component-wise (`tests` skips `tests/` not `tests.py`). |
| `--select RULES` | Review only the comma-separated rule IDs. Repeatable. |
| `--ignore RULES` | Skip the comma-separated rule IDs for this run without changing `avouch.toml`. |

**Inline suppression** — `# avouch: ignore[SCR002]` or `# noqa: SCR002` on the offending line (blanket `# avouch: ignore` / `# noqa` suppresses all on that line; any such line inside the function counts). File-level: `# avouch: ignore-file[SCR014]` at the top of the file.

---

## Commands

### `avouch init`

Measure repo maxima and write `avouch.toml` with `measured+1` headroom so the first run is `All clean`. `--dry-run` previews. Rerun recomputes.

```toml
ignore_paths = ["tests"]
[limits]
max_parameters = 6
max_file_lines = 450
```

### `avouch baseline`

Snapshot current findings to `.avouch/baseline.json` (`rule+file+name+line` fingerprint; moving a function re-flags). Commit it; later runs show only *new* findings.

```bash
avouch baseline          # snapshot full review (idempotent, recomputes)
avouch                   # only new findings
avouch --no-baseline     # show everything
```

`--verbose` shows `suppressed N finding(s) by baseline`; the `BY RULE` tally shows `(+N suppressed)`. Malformed or wrong version → `error: invalid baseline:` exit 2. Missing file → no suppression.

### `avouch rule [ID]`

Per-rule help from the same registry that backs `--docs`. `avouch rule` lists all 20 IDs; `avouch rule SCR002` shows one (name, description, scope, config, Bad/Good, severity). Unknown → `error: unknown rule 'FOO'` exit 2. Works outside a repo.

---

## Configuration

`avouch.toml` is found by walking upward from `CWD` to the filesystem root (so `tests/` picks up the repo root config). It is optional and partial — only the keys you set override defaults. Unknown keys are ignored silently; invalid values raise `error: invalid avouch.toml configuration` exit 2 (`limits` must be positive ints, `rules` bools, `ignore_paths` a list of strings). No env vars; only `AVOUCH_WATCH_INTERVAL` and `AVOUCH_FONT` are read.

```toml
[limits]        # thresholds per rule
[rules]         # on/off per rule (bool, default true)
ignore_paths = ["tests", "migrations"]
```

### Limits

| Key | Default | Rule | Meaning |
|-----|---------|------|---------|
| `max_parameters` | 5 | SCR014 | Max params |
| `max_nesting` | 5 | SCR013 | Max depth |
| `max_function_lines` | 300 | SCR012 | Function span |
| `max_class_lines` | 200 | SCR010 | Class span |
| `max_file_lines` | 1000 | SCR011 | File lines |
| `max_complexity` | 40 | CPLX | McCabe |
| `max_boolean_conditions` | 5 | SCR003 | Operands in chain |
| `max_if_chain` | 5 | SCR007 | If/elif length |
| `max_local_variables` | 30 | SCR009 | Assigned names |
| `max_return_statements` | 6 | SCR016 | Returns |
| `max_lambda_nodes` | 10 | SCR008 | Lambda nodes |
| `max_large_comprehensions` | 40 | SCR005 | Comprehension nodes |

Missing limit falls back to the hardcoded default — a partial config never disables a check.

### Rule toggles

All default to `true`.

| Key | Rule | | Key | Rule |
|-----|------|---|-----|------|
| `async_without_await` | SCR001 | | `max_class_lines` | SCR010 |
| `bare_except` | SCR002 | | `max_file_lines` | SCR011 |
| `max_boolean_conditions` | SCR003 | | `max_function_lines` | SCR012 |
| `detect_duplicateb` | SCR004 | | `max_nesting` | SCR013 |
| `max_large_comprehensions` | SCR005 | | `max_parameters` | SCR014 |
| `empty_except` | SCR006 | | `nested_function` | SCR015 |
| `max_if_else_chain` | SCR007 | | `max_return_statements` | SCR016 |
| `max_lambda_nodes` | SCR008 | | `mutable_default_args` | SCR017 |
| `max_local_variables` | SCR009 | | `shell_true` | SCR019 |
| `max_complexity` | CPLX | | `dynamic_code` | SCR020 |

### Ignoring paths

Component-wise: `tests` skips `tests/` but not `tests.py`; `"."` skips the repo. Sources are combined with `--ignore-path`, de-duplicated, and matched by string — no filesystem access.

---

## CI

### GitHub Actions

Use `--all-files` in CI; a fresh checkout has no diff, so the default scope finds nothing.

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
      - run: avouch --all-files --format github  # or: --format sarif > results.sarif
```

Non-zero exit fails the job, so findings surface as PR annotations. `permissions: contents: read` is enough. Pin `avouch==0.3.4`.

This repo ships `.github/workflows/avouch.yml` — enable it in **Actions**; it does `pip install -e .` and runs `--all-files --json` on PR and push.

### Pre-commit

```yaml
repos: [{repo: https://github.com/mukundzha/avouch, rev: v0.3.4, hooks: [{id: avouch}]}]
# .pre-commit-hooks.yaml: entry avouch --staged, pass_filenames: false
```

Baselined findings don't fail the hook.

### Any other CI

`pip install avouch` → `avouch --all-files --json` → check the exit code.

---

## How it works

`cli.py` only orchestrates:

```
load_config → git review set → analyzer.analyze_file (ast + walk cache + rules)
            → baseline.filter → report (or --json / --changed / --quiet)
```

`--docs` and `--version` short-circuit. See `avouch --docs` for the mermaid pipeline diagrams.

### Layout

```
avouch.toml  .avouch/baseline.json
src/avouch/
  cli.py              # entry, only orchestrates
  baseline.py         # snapshot + suppression
  git.py              # review set
  analyzer.py         # ast walk, dispatch
  report.py           # terminal / json / github / sarif / diff
  rules/              # one analyze(node, limits) per rule
  utility/            # walk, docs, suppress, measure, is_ignored, is_generated
  config/             # default.py (DEFAULT_LIMITS), loader.py (load_config)
tests/                # test_git.py, test_init.py
```

### Adding a rule

One file per rule exposing `analyze(node, limits) -> list[issue]`, where each issue is
`{"rule": "SCR017", "severity": "WARNING", "message": "Description (value/limit). Remediation."}`.
Then add the toggle to `DEFAULT_RULES` (plus a `DEFAULT_LIMITS` entry if it needs a threshold),
wire the call into `analyzer.py` behind a guard, and add violation + boundary tests. The renderer
handles any `(severity, message)`.

### Testing

```bash
pip install -e . && python -m pytest
```

100 tests, <1s, no network. Covers git helpers against a real temp repo, config validation
(upward discovery, positive-int limits, boolean rules, `ignore_paths` type), rule boundaries,
unreadable/syntax errors, report and diff rendering, `avouch rule`, `github`/`sarif` goldens,
and `--docs` outside a repo. Only `subprocess.run` is mocked.

---

## FAQ

**Changed files only?** Whole-repo review buries your few findings under legacy noise; the diff keeps it relevant to the next push.

**Why `git diff HEAD` not `git diff`?** Plain `diff` is unstaged only; `HEAD` covers staged + unstaged plus untracked, so nothing is missed.

**Why AST not regex?** Regex can't count cross-line parens, nesting depth, or distinguish `def` from a call. The AST answers exactly.

**Reviews, doesn't gate?** Exit `1` means findings, so CI *can* react — but the default workflow only annotates a PR rather than blocking it.

**Baseline vs `ignore_paths`?** `ignore_paths` hides files permanently; baseline hides *findings* as of the snapshot but re-flags them if moved. Use baseline for legacy debt.

**`init` vs `baseline`?** `init` sets limits to `measured+1` so the first run is clean; `baseline` snapshots findings. Compose both on greenfield.

**`rule` vs `--docs`?** Same registry — `--docs` prints all 20, `avouch rule SCR002` prints one.

## License

MIT — see `LICENSE`.