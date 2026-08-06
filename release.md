# scrut v0.3.0 — 11 new rules, stable rule identifiers, redesigned report

This release turns Scrut from a five-check diff reviewer into a full
structural analysis suite: **11 new rules**, stable **rule identifiers**
(`SCR001`–`SCR016`), per-rule **on/off toggles**, and a completely
**redesigned terminal report**.

## 11 new rules

Every rule now emits a stable identifier and a message with concrete
remediation guidance.

| ID | Rule | Metric | Scope |
|----|------|--------|-------|
| SCR001 | Async function without `await` | detected | async funcs |
| SCR002 | Bare `except:` | detected | funcs |
| SCR003 | Boolean expression too complex | `N/limit` | funcs, classes |
| SCR004 | Duplicate branch | detected | funcs |
| SCR005 | Large comprehension | `N/limit` | funcs |
| SCR006 | Duplicate branch (class scope) | detected | classes |
| SCR007 | Long if/elif chain | `N/limit` | funcs, classes |
| SCR008 | Lambda too complex | `N/limit` | funcs |
| SCR009 | Too many local variables | `N/limit` | funcs |
| SCR015 | Nested function definition | detected | funcs |
| SCR016 | Too many return statements | `N/limit` | funcs |

Function and class cyclomatic complexity checks round out the rule set.

## What else is new

- **Stable rule identifiers** — findings are now addressable by ID
  (`SCR001`–`SCR016`), not just message text.
- **Per-rule toggles** — a `[rules]` section in `scrut.toml` disables any
  rule without touching code.
- **`AsyncFunctionDef` analysis** — async functions are analyzed, not
  skipped.
- **One module per rule** — the rule engine was extracted into
  dedicated modules behind an `analyze(node, limits)` signature.
- **`SCRUT_FONT`** — opt-in terminal font switch (OSC 50).

## Redesigned report

- Summary header with counts: `🔴 errors · 🟡 warnings · 🟢 passed ·
  📊 funcs checked`
- Per-file tables with `Component · Kind · Rule · Metric` columns
- Width-aware layout that truncates long values and never wraps
- `detected` placeholder for threshold-free rules
- Collapsed `[PASSING]` grid that adapts to terminal width
- Alignment correct for emoji and wide glyphs

```text
scrut [Review Summary]
╔═════════════════════════════════════════╗
║ 🟡 3 warnings      │ 📊 3 funcs checked ║
╚═════════════════════════════════════════╝

[NEEDS REVIEW] ────────────────────────────────────────────────────────────

╭─ ⚠️ buggy.py (3)
│  Component  Kind  Rule                                         Metric
│  ────────────────────────────────────────────────────────────────────
│  handle     func  Nesting too deep                                5/4
│  fake       func  Async function contains no await expression  detected
│  extra      func  Too many parameters                             6/5
```

## Breaking changes

None. The CLI surface is unchanged — `scrut`, no arguments, exit code
always `0`.

## Upgrading

```bash
pip install --upgrade scrut
```

## Links

- [README](https://github.com/mukundzha/scrut#readme)
- [Changelog](CHANGELOG.md)
- [Issues](https://github.com/mukundzha/scrut/issues)
