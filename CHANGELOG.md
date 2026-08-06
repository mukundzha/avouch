# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog.

## [0.3.0]

### Added
- Stable rule identifiers: every rule now carries an ID in the
  `SCR001`–`SCR016` range.
- Per-rule toggles via a `[rules]` section in `scrut.toml`, so any rule
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
- `SCRUT_FONT` environment variable to request an optional terminal font
  switch (OSC 50) for the report.

### Changed
- Modularized inline analysis logic into a dedicated rule module per
  rule, each behind an `analyze(node, limits)` signature.
- Redesigned report rendering:
  - summary header with per-severity counts and a passing-files count
  - table per file with Component / Kind / Rule / Metric columns
  - width-aware layout that truncates long values and never wraps
  - collapsed `[PASSING]` grid that adapts to the terminal width
  - redundant "detected" wording removed from rule labels (kept in the
    Metric column)
  - alignment fixed for emoji and wide glyphs
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