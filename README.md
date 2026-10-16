# avouch

**Review the Python you changed, not the Python you inherited.**

[Docs](https://pypi.org/project/avouch) · [Changelog](CHANGELOG.md) · [Source](https://github.com/mukundzha/avouch) · [Issues](https://github.com/mukundzha/avouch/issues)

## Install

```bash
pip install avouch
```

Python 3.10+ · `git` on `PATH` · zero dependencies · no daemon, no network

## Review

```bash
avouch                            # changed vs HEAD + untracked
avouch --staged                   # staged only — pre-commit
avouch --all-files --format github  # PR annotations in CI
```

```text
AVOUCH · 2 FILES · 1 WARN
──────────────────────────────────────────────
bad.py:1: SCR002: Bare except detected.
  │
1 │ def connect(host, port):
  │     ^^^^^^^ SCR002
BY RULE  SCR002 Bare except 1
PASSED  ✓ src/util.py
```

Findings land only on functions and classes whose span overlaps a changed line — legacy debt never reaches your diff. Exit codes: `0` clean · `1` findings · `2` error.

## Configure

```toml
ignore_paths = ["tests"]
[limits]
max_parameters = 8
[rules]
nested_function = false
```

`avouch init` measures your repo and writes this for you. 20 rules, every threshold tunable, every finding suppressible inline. Full catalog: `avouch --docs`.

## Contribute

```bash
git clone https://github.com/mukundzha/avouch && cd avouch
pip install -e . && python -m pytest
```

Open a PR — CI runs `avouch` against itself.

## License

MIT