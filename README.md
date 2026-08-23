# avouch

**Review the Python you changed, not the Python you inherited.**

Avouch reviews only files your next commit touches — `git diff HEAD` + untracked `.py`, parsed with `ast`. No daemon, no network.

```bash
pip install avouch
avouch
```

## Why

Paid AI reviewers buried my diff under legacy noise. Avouch runs locally before `git push`, costs nothing, shows only your changes.

## Install

Python 3.10+ and `git` required.

```bash
pip install avouch
# or
git clone https://github.com/mukundzha/avouch.git && cd avouch && pip install -e .
```

## Quick start

```text
$ avouch
AVOUCH · 2 FILES · 4 WARN
bad.py:1: SCR002: Bare except detected.
  │
1 │ def connect(host, port, ...):
  │     ^^^^^^^ SCR002
BY RULE  SCR002 Bare except 1
PASSED  ✓ src/util.py

$ avouch
All clean.
```

Compiler-style `file:line` + caret, `BY RULE` tally, capped `PASSED` grid.

Flags: `--json` `--docs` `--changed` `--staged` `--all-files` `--not-git` `--quiet` `--verbose` `baseline` `--no-baseline` `rule`

Review set = changed + untracked `.py`; skips deleted/non-py/generated. Exit `0` clean, `1` findings, `2` error. `avouch --docs` is the docs of record (TTY browser, piped plain).

## JSON

```bash
avouch --json
# {"version":1,"tool":"avouch","violations":[{"rule":"SCR014","file":"buggy.py","line":4}],"summary":{"total":1}}
```

Deterministic, no colors. Same exit codes — gate CI on exit code + parse stdout.

## Quiet

`--quiet` same analysis, only exit code. Errors/`--json`/`--verbose` still emit.

## GitHub Actions

```yaml
- uses: actions/checkout@v6
- uses: actions/setup-python@v5
  with: {python-version: "3.12"}
- run: pip install avouch
- run: avouch --all-files --json
```

Use `--all-files` in CI (fresh checkout has no diff).

## Pre-commit

```yaml
repos: [{repo: https://github.com/mukundzha/avouch, rev: v0.3.3, hooks: [{id: avouch}]}]
```

## Baseline

```bash
avouch baseline        # snapshot to .avouch/baseline.json
avouch                 # only new findings
avouch --no-baseline   # show all
```

Fingerprint `rule+file+name+line`. Commit `.avouch/baseline.json`. `--verbose` shows suppressed, `BY RULE` shows `(+N suppressed)`.

## Configuration

`avouch.toml` walks upward from CWD to root, optional/partial, merged over defaults. Invalid `limits`/`rules`/`ignore_paths` → `error: invalid avouch.toml configuration` exit 2.

```toml
[limits] max_parameters = 8
[rules] nested_function = false
ignore_paths = ["tests"]
```

See `avouch --docs` for full table. `--ignore-path` appends. No env vars.

## How it works

`cli.py` only orchestrates. Pipeline: `load_config` → `git` review set → `analyzer` → `baseline` → `report`/`--json`/`--changed`. See `avouch --docs` for diagrams.

## Layout

```
avouch.toml  .avouch/baseline.json
src/avouch/cli.py  baseline.py  git.py  analyzer.py  report.py
src/avouch/rules/*.py  utility/walk.py  utility/docs.py  config/
tests/test_git.py  test_init.py
```

## Adding a rule

`src/avouch/rules/<name>.py` → `analyze(node, limits) -> list[issue]`. Add toggle in `DEFAULT_RULES` (+limit if needed), wire in `analyzer.py`, add tests.

## Testing

```bash
pip install -e . && python -m pytest
```

86 tests, <1s, real temp git repo. Only `subprocess.run` mocked.

## FAQ

**Changed files only?** Keeps output relevant. **git diff HEAD?** Includes staged+untracked. **AST?** Exact vs regex. **Exit codes?** 0/1/2. **Network?** No.

## License

MIT — see `LICENSE`.
