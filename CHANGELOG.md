# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog.

## [0.3.3] - 2026-08-23

### Added
- `avouch init`: measure repo maxima and write `avouch.toml` clean-by-construction (`measured+1`, `--dry-run`).
- `avouch baseline`: snapshot findings to `.avouch/baseline.json` (`rule+file+name+line` fingerprint), filter before render/exit, `--no-baseline` to bypass; `BY RULE (+N suppressed)` and `--verbose` suppressed count.
- Parallel review: `ProcessPoolExecutor` for `>8` files (`AVOUCH_WORKERS`/`SCRUT_WORKERS`, `min(cpu,8)`), order-preserved, serial fallback for small diffs.
- CI-native formats: `--format github` (`::warning/::error file=,line=,col=,title=`) and `--format sarif` (SARIF 2.1.0 with `tool.driver.rules` and `physicalLocation` spans); mutually exclusive with `--json`/`--changed`.
- `avouch rule [ID]`: per-rule help from single `RULES` registry in `utility/docs.py` (SCR001-017 + complexity), `avouch rule` lists all, unknown → exit 2.
- Pre-commit hook: `.pre-commit-hooks.yaml` (`avouch --staged`, `pass_filenames: false`).
- Diff annotations: `avouch --changed` now annotates findings inline at hunk lines with caret/column, handling orphans and file-level.

### Changed
- Configuration hardening: `avouch.toml` discovered by walking upward from CWD to FS root, `limits` must be positive ints, `rules` booleans, `ignore_paths` list of strings; unknown keys ignored; malformed/invalid → `error: invalid avouch.toml configuration` exit 2 with key, never `internal error`.
- `avouch --verbose` now shows resolved config path (`config: <resolved-path>`) and baseline suppressed count.
- Report `BY RULE` now shows `(+N suppressed)` and `PASSED` grid still capped.
- `README.md` slimmed to landing (496w); full docs live in `avouch --docs` (`utility/docs.py`).

### Fixed
- `avouch rule` and `--format` help and error hints now correctly short-circuit before config/git.
- Column calculation for `github`/`sarif` now correctly finds `def`/`class` name (col 5 for `def f`, 7 for `class Foo`) instead of first `f` in `def`.

## [0.3.2]

### Added
- `--not-git`: review every eligible `.py` file on disk without a Git
  repository.
- Review scopes `--all-files` (whole repository) and `--staged` (index
  only), plus the explicit `--changed` diff view of files vs `HEAD`.
- `--quiet` (exit code only), `--verbose` (step-by-step diagnostics),
  `--json` (stable, versioned machine-readable document), `--version`.
- `--ignore-path` CLI flag, combined with `ignore_paths` from
  `avouch.toml`.
- Rule-grouped findings summary: a `BY RULE` section counting the most
  common issues across the review.
- GitHub Actions workflow in the repository itself (`avouch` reviews its
  own code on every push and pull request).
- Interactive terminal browser for `--docs`; piped output prints plain
  text.

### Changed
- Findings render with source context: each finding prints a `file:line` header,
  the rule id, the full message, and the offending code region with a
  caret under the flagged name (compiler-style output).
- Terminal report redesigned; findings render once per rule/component in
  a single pass.
- AST walks are cached per file, and dead depth traversal was removed —
  analysis of large repositories is roughly twice as fast.
- Configuration is parsed once per process and reused, keyed by file
  mtime and size; edited `avouch.toml` files bust the cache.
- Report records carry an explicit `kind` (`func`/`class`/`file`)
  instead of shape sniffing.
- Errors route to stderr; conflicting review-scope flags are rejected
  with a hint.

### Fixed
- Documentation caught up with the implementation: rule limits, hints,
  and test counts now match the shipped behavior.
- Default limits relaxed to match `avouch.toml` so whole-repo CI checks
  pass on the repository itself.
- The repository's own whole-repo scan is clean: node-dispatch logic was
  extracted out of `analyze_file` (nesting deep enough to trip SCR013)
  and the rule-summary sort uses a named key function instead of a
  complex lambda (SCR008).

## [0.3.0]

### Added
- Stable rule identifiers: every rule now carries an ID in the
  `SCR001`–`SCR016` range.
- Per-rule toggles via a `[rules]` section in `avouch.toml`, so any rule
  can be disabled without touching code.
- New rules (11 new rule IDs; the five v0.2 checks were carried over):
  - `SCR001` async function without `await` expression
  - `SCR002` bare `except`
  - `SCR003` boolean expression too complex
  - `SCR004` duplicate branch detection
  - `SCR005` large comprehension
  - `SCR006` duplicate branch (class scope)
  - `SCR007` long if/elif chain
  - `SCR008` lambda too complex
  - `SCR009` too many local variables
  - `SCR015` nested function definition
  - `SCR016` too many return statements
- Cyclomatic complexity checks for functions and classes
  (`Function too complex`, `Class too complex`).
- `AsyncFunctionDef` nodes are now analyzed.
- `AVOUCH_FONT` environment variable to request an optional terminal font
  switch (OSC 50) for the report.

### Changed
- Modularized inline analysis logic into a dedicated rule module per
  rule, each behind an `analyze(node, limits)` signature.
- Redesigned report rendering with a minimal Rich-based terminal UI:
  - bold project header with file / issue / finding counts
  - per-file breakdown with bold function names and dim rule identifiers
  - grouped findings per function with whitespace-driven indentation
  - width-aware message truncation that never wraps
  - rule-aligned summary section ordered by frequency with passing-file count
- Improved rule messages with concrete remediation guidance.

### Fixed
- Report column alignment with wide characters and emoji.

## [0.2.0] - 2026-08-01

### Added
- Modular project architecture.
- Configurable analysis limits.
- Redesigned CLI interface.
- Cleaner report rendering.

### Changed
- Refactored the codebase into dedicated modules.
- Improved AST analysis pipeline.
- Improved Git-aware review workflow.
- Improved project maintainability.

### Internal
- Better separation of concerns.
- Cleaner code organization.
- Foundation for future analysis rules and CI integration.

## [0.1.1]

### Fixed
- Minor improvements and bug fixes.

## [0.1.0]

### Added
- Initial public release.
- Git-aware Python static code review.
- AST-based analysis.
- Function, class, and file-level checks.