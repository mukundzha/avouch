# Scrut Roadmap — v0.3.3

**Theme: "First run clean. Every run relevant."**

This roadmap is the plan for the v0.3.3 release. Every item below is scoped to
land in one milestone, ships with tests written before the code, and must
survive the philosophy section of the README.

---

## 1. Vision

Scrut does not compete with ruff on its battlefield. Ruff is the linter for
your whole codebase: 800+ rules, Rust speed, autofix, a formatter, and a
company behind it. Fighting over rule count or raw speed is a lost war.

Scrut occupies the niche ruff structurally cannot enter:

> **The review of your next push.**

The report is the diff. Every finding is attributable to work you are about
to push — never to the legacy you inherited. Runtime is proportional to your
diff, not your repository. You keep authority: scrut reviews, it never gates.

### Positioning vs ruff

| Axis | ruff | scrut |
|------|------|-------|
| Review set | Everything you tell it | Git-native: only files about to change |
| Runtime | Proportional to repo size | Proportional to your diff |
| First run | Wall of legacy debt | `scrut init` — clean by construction |
| Every run | All findings, always | Baseline — only *new* findings |
| Metrics | Fixed thresholds | Measured from your reality |
| Output | Terse violation frames | Compiler-style: file:line + caret + context |
| Posture | Gates by default | Reviews; enforcement stays yours |

### What we concede (explicitly)

Whole-repo speed, rule breadth, autofix, formatting, ecosystem. These fights
are lost before they start — and saying so in public is part of the product:
scrut's one job is the seconds before `git push`.

---

## 2. The 8 implementations

### IMPL 1 — Configuration hardening

**What it is.** Today a malformed `scrut.toml` fails at analysis time with an
internal error (exit 2), values are not type-checked, and configuration only
looks at the current working directory. This implementation makes
configuration dependable before anything else is built on top of it:
readable validation errors, and upward search for `scrut.toml`.

**How we'll make it.**
- In `loader.py`, after `tomllib.load`, validate every key against the
  `DEFAULT_LIMITS` / `DEFAULT_RULES` / `ignore_paths` schema:
  - limits must be positive integers (reject strings, floats, booleans)
  - rules must be booleans
  - `ignore_paths` must be a list of strings
  - unknown keys are ignored (documented behavior, unchanged)
- Validation errors raise `ValueError` with a precise message
  (`invalid scrut.toml configuration: limits.max_parameters must be a
  positive integer; got "eight"`); `cli.py` already maps that to exit 2 with
  a hint — extend the hint to echo the offending key.
- Upward search: `Path.cwd()` walks parent directories until `scrut.toml` is
  found or the filesystem root is reached. Cache the resolved path alongside
  the existing mtime/size cache so a subdirectory run shares the config.
- `--verbose` reports which config file was used (path or `defaults`).

**Tests (before code).**
- Malformed TOML: exit 2, readable message, no internal-error text.
- Wrong types: `max_parameters = "eight"` → exit 2 with the key named.
- Out-of-range: `max_parameters = 0` and negatives are rejected as invalid.
- Upward search: config in repo root applies to a run from `tests/`.
- CLI `--ignore-path` still appends to the upward-found config.

**Acceptance.** Every invalid-config path exits 2 with a readable message,
and no run ever says `internal error` because of configuration.

---

### IMPL 2 — `scrut init`: clean-by-construction onboarding

**What it is.** A one-command bootstrap: measure the current repository's
maximums for every limit (parameter count, nesting depth, function lines,
complexity, …), write a `scrut.toml` whose limits are that measured reality,
so the first run is **clean by construction**. Onboarding time-to-first-
clean-run goes from "minutes of triage" to "one command."

**How we'll make it.**
- New `scrut init` CLI command (mutually exclusive with review flags).
- New `utility/measure.py`: a single module that walks each reviewable file
  once and computes every limit metric directly from the AST — reusing the
  existing primitives (`get_depth`, `calculate_complexity`, node
  `lineno`/`end_lineno`, `len(node.args.args)`, comprehension/if-chain/
  return/lambda counters already implemented in the rule modules). Rules are
  the spec, so metrics are computed exactly the same way they are flagged.
- Headroom policy: limit = measured maximum + 1, unless the measured maximum
  is 0 (no evidence) in which case use the current default. Rationale: the
  review set is the diff — legacy peaks may repeat, so one unit of headroom
  absorbs them while new violations still trigger.
- `scrut init --dry-run` prints the would-be `scrut.toml` without writing;
  `scrut init` writes the file and prints the summary
  (`scrut.toml written: measured 12 maxima across N files`).
- Rerunning `scrut init` recomputes from scratch (no incremental state).

**Tests (before code).**
- Probe repo with known maxima → generated TOML contains measured+1.
- Zero-evidence rules keep defaults.
- `--dry-run` does not create the file.
- After `scrut init`, `scrut --all-files` exits 0 on the same repo.
- Adding a worse-than-limit function afterwards reports exactly that
  finding — the baseline philosophy survives.

**Acceptance.** A fresh clone, `pip install scrut`, `cd repo`, `scrut init`,
`scrut`: exit 0, output "All clean."

---

### IMPL 3 — Baseline: "only new findings"

**What it is.** The logical completion of "review the Python you changed":
a baseline snapshot of current findings stored in `.scrut/baseline.json`,
auto-suppressed on subsequent runs. The report then shows **only findings
that did not exist at baseline time** — the diff-of-findings. This is the
feature ruff structurally cannot ship: suppression is not silence, it is
history.

**How we'll make it.**
- New `scrut baseline` command: runs the full review, writes
  `.scrut/baseline.json` (schema `{"version": 1, "findings": [...]}`), where
  each entry carries a stable fingerprint:
  `rule + file + item name + line`. The fingerprint is content-based, not
  hash-of-source, so moving a function changes the fingerprint and re-flags
  the finding honestly.
- `.scrut/baseline.json` is committed to the repository (it is shared
  intent, like `scrut.toml`); note this in `.gitignore` documentation.
- Runtime suppression: `cli.py` loads the baseline (mtime/size cache, same
  pattern as config), then filters reports *before* rendering and *before*
  exit-code computation. Suppressed findings are counted and reported in
  `--verbose` and in the BY-RULE section as
  `(+N suppressed by baseline)`.
- `--no-baseline` disables suppression; `scrut baseline` is idempotent
  (recomputes the snapshot from scratch).
- `scrut init` + `scrut baseline` compose: init makes the first run clean,
  baseline makes every later run only-new.

**Tests (before code).**
- Baseline on a dirty repo → second run clean, exit 0.
- Introducing a new violation → exactly that finding, still exits 1.
- Editing an existing finding's line (fingerprint change) → re-flagged.
- `--no-baseline` shows all findings again.
- Baseline file with wrong version or malformed JSON → exit 2, readable
  error, never a traceback.

**Acceptance.** `scrut baseline` once; every run after that reports only
findings introduced since the baseline — in CI and locally identically.

---

### IMPL 4 — Parallel review

**What it is.** Today files are analyzed serially: a 200-file repository
takes ~25s. Review runs must finish in seconds. Impl 4 moves file analysis
into a worker pool while keeping output byte-identical to the serial path.

**How we'll make it.**
- Replace the `for file_path in reviewable_files: analyze_file(...)` loop in
  `cli.py` with `concurrent.futures.ProcessPoolExecutor` using `executor.map`
  — `map` preserves input order, so reports keep the current deterministic
  ordering with no sorting hacks.
- Workers receive `(file_path, limits, rules)`; `limits`/`rules` are plain
  dicts (picklable); `reset_walk_cache()` already runs per file inside
  `analyze_file`, so worker caches cannot leak between files.
- zlib/thread resource: the config mtime/size cache is process-local and
  already keyed by stat — harmless when recomputed per worker.
- Default pool size: `min(os.cpu_count(), 8)` — bounded by design
  (`SCRUT_WORKERS` env override, `1` forces serial for debugging).
- Keep the serial path exactly as today when the reviewable set is small
  (≤ 8 files: pool startup overhead is not worth it).

**Tests (before code).**
- Equality test: parallel output (report text and `--json`) is byte-identical
  to serial output on the same fixture tree.
- Determinism: two parallel runs produce identical output.
- `SCRUT_WORKERS=1` reproduces serial behavior.
- Findings/exit codes unaffected.

**Acceptance.** `scrut --all-files` on this repository's 200+ files completes
in ≤ 8s wall time (today ~25s), with output identical to serial.

---

### IMPL 5 — CI-native output formats

**What it is.** GitHub Actions users need inline annotations, and secure
workflows need SARIF. Impl 5 ships `--format=github` (workflow commands that
render as annotations on the diff) and `--format=sarif` (SARIF 2.1.0,
accepted by GitHub code scanning and every major CI). JSON output stays
stable.

**How we'll make it.**
- `report.py` gains two renderers alongside `render_json`:
  - `render_github(reports)`: emits `::warning file=…,line=…,col=…,title=…::`
    workflow-command lines (ERROR findings use `::error`). Columns come from
    the existing caret logic (already computes the offending name's column
    in `_render_finding` — extract it into a shared helper).
  - `render_sarif(reports)`: SARIF 2.1.0 with `runs[0].tool.driver`
    (name, version, 16+ rules + complexity checks), and `results[]` with
    `rule_id`, `level` (warning/error), `message`, and
    `physicalLocation` (uri + startLine/startColumn/endLine/endColumn).
- `cli.py`: `--format github|sarif` flag, mutually exclusive with `--json`
  and `--changed`; exit codes unchanged (reports still drive the gate).
- Column data feeds both formats and the terminal caret — one source of
  truth for spans, extracted into a shared `spans.py` helper.
- `--json` schema is untouched (v1, stable): CI formats are additive.

**Tests (before code).**
- GitHub format: golden output matches workflow-command syntax exactly;
  ERROR findings emit `::error`, everything else `::warning`.
- SARIF: result parses, mandatory 2.1.0 keys present, rule IDs match
  SCR001–SCR016, line/column spans match the caret positions.
- Flags are mutually exclusive (exit 2 with hint on conflict).
- Exit codes unchanged in all formats.

**Acceptance.** A GitHub Actions job using `scrut --format=github` shows
inline annotations on the touched lines; a SARIF upload produces code
scanning alerts with correct locations.

---

### IMPL 6 — `scrut rule`: per-rule man pages

**What it is.** `ruff rule`-parity for documentation: `scrut rule SCR002`
prints one rule's full entry (what it detects, why it matters, example of
bad and good code, config key), identical content to what `--docs` shows.
One source of truth, two surfaces.

**How we'll make it.**
- Introduce a rule registry in the docs layer (`utility/docs.py` today
  holds the prose): a structured `RULES` table
  (`id → {name, description, example_bad, example_good, config_key,
  severity}`) that both `render_docs()` and the new command render from.
  Refactor, do not duplicate.
- `cli.py`: `scrut rule <ID>` subcommand. Unknown ID → exit 2 with hint
  (`unknown rule; try 'scrut --docs' or 'scrut rule SCR013'`). `scrut rule`
  with no argument lists all IDs.
- `scrut --docs` still renders the full page, now generated from the same
  registry — content parity is guaranteed by construction.

**Tests (before code).**
- Every SCR001–SCR016 exists in the registry and is reachable via
  `scrut rule`.
- Rendered `scrut rule SCR002` contains name, description, example, config
  key, and matches the corresponding `--docs` section.
- Unknown ID exits 2; bare `scrut rule` lists all rules.

**Acceptance.** No rule is undocumented, and the documentation cannot drift
between `--docs` and `scrut rule` — the registry is the single source.

---

### IMPL 7 — pre-commit hook

**What it is.** A first-class pre-commit integration:
`.pre-commit-hooks.yaml` that runs scrut on staged files, review-only
(no gating config, exit code is transparent about findings).

**How we'll make it.**
- `.pre-commit-hooks.yaml` at the repository root:
  `id: scrut`, `name: scrut`, `entry: scrut --staged`, `language: python`,
  `types: [python]`, `pass_filenames: false` (scrut already computes the
  review set from git — it must not receive file lists twice).
- README gains the pre-commit install block (`- repo:
  https://github.com/mukundzha/scrut` + `rev` + `hooks: [scrut]`).
- post-commit philosophy is preserved: the hook reports findings; teams
  that want enforcement pair it with `--fail-on-findings`-style CI config —
  the hook itself never rewrites or blocks beyond the exit code.
- Baseline (IMPL 3) composes with the hook automatically: suppressed
  findings do not fail the hook.

**Tests (before code).**
- Run the hook entry directly (`pre-commit run scrut --files` on a fixture
  repo, and the bare entry) — staged review set, correct exit codes
  (0 clean / 1 findings / 2 error).
- Untracked staged files are reviewed; ignored paths are not.
- `pass_filenames: false` verified by a run with explicit file args.

**Acceptance.** `pre-commit run scrut` works on a fresh install per the
README block and reports exactly the staged review set.

---

### IMPL 8 — Review-mode diff view: the sketch of a PR, locally

**What it is.** `scrut --changed` today prints the diff; findings live in a
separate report. Impl 8 merges them: the changed-files view annotates each
finding **inline at its line inside the diff**, with the rule ID and message
under the offending line — a local draft of a PR review comment thread, with
`+`/`-` context preserved. This is the demo feature: one screen, the whole
story.

**How we'll make it.**
- `render_diff_view` gains a findings map: `line → [rule_id, message]`
  built from the analyzed changed files (the same reports `--json` uses).
- During hunk rendering, after a line that carries findings, print the
  annotation block (`rule_id` in blue, message dimmed) indented to the
  line column — reusing the caret/column helper from IMPL 5.
- Layout rules: one annotation line per finding per line; context lines
  (`ctx`) that carry findings show them too (a finding can be on an
  unchanged line near the hunk); the `+`/`-`/` ` gutter stays intact so
  the diff remains readable.
- Findings on files with no diff (untracked new files) render as full-file
  annotations below the file header.
- `--changed --json` remains available (annotation view stays a terminal
  rendering concern).

**Tests (before code).**
- Fixture with a finding on an added line → annotation appears under it at
  the correct column, gutter preserved.
- Finding on a context line near a hunk → shown once, no duplicates.
- No findings → view byte-identical to today's diff view.
- Exit codes unaffected.

**Acceptance.** A single `scrut --changed` screen shows: file header with
+-/-- counts, the hunk, and every finding pinned at its exact line — the
local sketch of the PR review.

---

## 3. Milestones

| Milestone | Implementations | Definition of done |
|-----------|----------------|-------------------|
| M1 — Solid ground | 1 (config hardening), 2 (`scrut init`) | All new tests green; 74 existing tests still green; self-scan of this repo clean; README + `--docs` in sync |
| M2 — New-findings engine | 3 (baseline), 4 (parallel) | Acceptance metrics met (≤8s/200 files, only-new reports) |
| M3 — Into CI | 5 (github + sarif formats) | Annotations verified in a real Actions run; SARIF parses |
| M4 — Ships as a product | 6 (`scrut rule`), 7 (pre-commit), 8 (diff review) | Demo-ready `--changed` screen; CHANGELOG + version bump wired for v0.3.3 |

Sequencing is deliberate: M1 hardens the ground everything else sits on,
M2 delivers the identity features (first-run-clean, only-new), M3 makes CI
usability real, M4 is the polish that makes the release demo-ready.

## 4. Explicitly not in v0.3.3

| Item | Why not |
|------|---------|
| Semantic autofix | Scrut reviews, it does not rewrite your code — fixing is yours |
| Plugin/rule-count ecosystem | The ceiling is raised deliberately, not by accretion |
| Daemon / watch mode | Runtime is the standard library, no process to keep alive |
| `# scrut: ignore` comments | Inline suppression hides systemic debt; baseline is the honest mechanism |
| Formatting | Out of scope on purpose: formatting is not review |

## 5. Success metrics for v0.3.3

- **Time to first clean run** — from `pip install scrut` to "All clean":
  under 60 seconds, zero config (IMPL 2).
- **% of findings attributable to your diff** — 100%, by construction; the
  baseline (IMPL 3) extends the promise from "the files you changed" to
  "the findings you introduced."
- **Pre-push runtime** — ≤8s for a 200-file repository (IMPL 4); typical
  changed-file reviews should feel instant.
- **CI presence** — inline annotations and SARIF accepted by default
  (IMPL 5), pre-commit one-liner (IMPL 7).

## 6. Working agreements

- **Tests before code** — every implementation above lists its tests first;
  a feature without a failing-then-passing test does not land.
- **README is the spec** — implementation changes update README and
  `--docs` in the same commit (docs.py mirrors the README).
- **Conventional commits** — `feat:`, `fix:`, `refactor:`, `docs:`,
  `perf:`, `chore:`; CHANGELOG updated per release.
- **Philosophy section wins** — any implementation that cannot survive the
  README philosophy (reviews, doesn't gate; exact metrics; stdlib runtime,
  diff-native review set) is cut, not bent.