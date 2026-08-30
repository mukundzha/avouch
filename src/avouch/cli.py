import argparse
import concurrent.futures
import importlib.metadata
import os
import shutil
import sys
import tokenize
import tomllib
import traceback
from pathlib import Path

from rich.console import Console
from rich.pager import Pager
from rich.syntax import Syntax

from avouch.config.loader import DEFAULT_RULES, load_config
from avouch.config.default import DEFAULT_LIMITS
from avouch.analyzer import analyze_file
from avouch.report import generate_report, render_diff_view, render_github, render_json, render_sarif, vlog
from avouch.utility.docs import render_docs
from avouch.utility.docs import RULES as DOC_RULES
from avouch.git import (
    DISK_SKIP_DIRS,
    get_all_files,
    get_all_files_on_disk,
    get_changed_files,
    get_changed_line_ranges,
    get_reviewable_files,
    get_staged_files,
    is_gitrepo,
)
from avouch.utility.measure import measure_maxima
from avouch.baseline import load_baseline, filter_reports, write_baseline
from avouch.fix import fix_bare_except, fix_mutable_default_args

SUCCESS = 0
VIOLATIONS_FOUND = 1
ERROR = 2

try:
    AVOUCH_VERSION = importlib.metadata.version("avouch")
except importlib.metadata.PackageNotFoundError:
    AVOUCH_VERSION = "0.3.4"


def _nothing_to_review_hint(args, candidate_files):

    if args.not_git:
        return "no reviewable .py files found on disk"
    if not candidate_files and not args.staged:
        return "nothing changed vs HEAD (CI checkouts are clean); use --all-files for a full review"
    return "change or stage .py files, or use --all-files"


def _parallel_target(payload):
    path, limits, rules = payload
    return analyze_file(path, limits, rules)


def _worker_count(n):
    if n <= 8:
        return 1
    raw = os.environ.get("AVOUCH_WORKERS") or os.environ.get("SCRUT_WORKERS")
    if raw is not None:
        try:
            v = int(raw)
            return v if v >= 1 else 1
        except ValueError:
            return 1
    c = os.cpu_count() or 1
    return min(c, 8)


class _DisplayPager(Pager):
    def show(self, content):
        if not (sys.stdin.isatty() and sys.stdout.isatty() and os.name == "posix"):
            sys.stdout.write(content)
            return

        import termios
        import tty

        lines = content.splitlines()
        page_size = max(shutil.get_terminal_size((80, 24)).lines - 1, 1)
        offset = 0
        old_settings = termios.tcgetattr(sys.stdin)

        try:
            tty.setcbreak(sys.stdin.fileno())
            while True:
                sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.write("\n".join(lines[offset : offset + page_size]))
                sys.stdout.write(
                    f"\n\n-- lines {offset + 1}-{min(offset + page_size, len(lines))}"
                    " (q quit, space next, b previous) --"
                )
                sys.stdout.flush()
                key = sys.stdin.read(1)

                if key == "q" or key == "\x03":
                    break
                if key in (" ", "f", "j", "\r", "\n"):
                    offset = min(max(len(lines) - page_size, 0), offset + page_size)
                elif key in ("b", "k"):
                    offset = max(0, offset - page_size)
                elif key == "g":
                    offset = 0
                elif key == "G":
                    offset = max(len(lines) - page_size, 0)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.flush()


def _display_file(file_path):
    path = Path(file_path)

    if not path.is_file() and len(path.parts) == 1:
        matches = sorted(
            candidate
            for candidate in Path.cwd().rglob(path.name)
            if candidate.is_file()
            and not any(part in DISK_SKIP_DIRS for part in candidate.parts)
        )
        if len(matches) == 1:
            path = matches[0]
        elif len(matches) > 1:
            names = ", ".join(str(match.relative_to(Path.cwd())) for match in matches)
            print(
                f"error: multiple files named '{file_path}' found: {names}",
                file=sys.stderr,
            )
            print("hint: use a relative path to select one", file=sys.stderr)
            return ERROR

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not display '{file_path}': {exc}", file=sys.stderr)
        return ERROR

    lexer = Syntax.guess_lexer(str(path), source)
    syntax = Syntax(
        source,
        lexer,
        line_numbers=True,
        word_wrap=False,
        indent_guides=True,
    )

    console = Console()
    with console.pager(pager=_DisplayPager(), styles=True):
        console.print(syntax)
    return SUCCESS


def _rule_filter_values(values):
    rule_keys = {}
    for rule_id, spec in DOC_RULES.items():
        rule_keys[rule_id] = spec["config_key"]

    result = []
    for value in values or []:
        result.extend(part.strip().upper() for part in value.split(",") if part.strip())

    unknown = [rule_id for rule_id in result if rule_id not in rule_keys]
    if unknown:
        raise ValueError(f"unknown rule '{unknown[0]}'")
    return {rule_keys[rule_id] for rule_id in result}


def _filter_changed_reports(functions, files, classes, line_ranges):
    def keep(report):
        if report["kind"] == "file":
            return True
        start = report.get("line")
        end = start + report.get("lines", 1) - 1 if start else start
        return any(
            start <= changed_end and end >= changed_start
            for changed_start, changed_end in line_ranges.get(report["file"], [])
        )

    return (
        [report for report in functions if keep(report)],
        files,
        [report for report in classes if keep(report)],
    )


def _snapshot_files(file_paths):
    snap = {}
    for fp in file_paths:
        try:
            st = Path(fp).stat()
            snap[fp] = (st.st_mtime_ns, st.st_size)
        except OSError:
            snap[fp] = None
    try:
        from avouch.config.loader import find_config_path
        cfg = find_config_path()
        if cfg is not None:
            try:
                st = cfg.stat()
                snap[str(cfg)] = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass
    except Exception:
        pass
    try:
        bf = Path(".avouch/baseline.json")
        if bf.exists():
            try:
                st = bf.stat()
                snap[str(bf)] = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass
    except Exception:
        pass
    return snap


def _run_single_review(args, ignore_paths, selected_rules, ignored_rules):
    try:
        config = load_config()
    except ValueError as exc:
        print(f"error: invalid avouch.toml configuration: {exc}", file=sys.stderr)
        print(f"hint: check the [limits], [rules], and ignore_paths sections ({exc})", file=sys.stderr)
        return ERROR, [], "config error"
    rules = config.get("rules", DEFAULT_RULES)
    if args.select:
        rules = {key: enabled and key in selected_rules for key, enabled in rules.items()}
    for key in ignored_rules:
        if key in rules:
            rules[key] = False
    limits = config.get("limits", DEFAULT_LIMITS)
    cur_ignore = config.get("ignore_paths", []) + (args.ignore_path or [])
    cur_ignore = list(dict.fromkeys(cur_ignore))
    if not args.not_git and not is_gitrepo():
        print("error: no Git repository found", file=sys.stderr)
        print("hint: run Avouch from inside a Git repository, or use --not-git to review files without Git", file=sys.stderr)
        return ERROR, [], "no git"
    if args.not_git:
        candidate_files = get_all_files_on_disk()
    elif args.all_files:
        candidate_files = get_all_files()
    elif args.staged:
        candidate_files = get_staged_files()
    else:
        candidate_files = get_changed_files()
    reviewable_files = get_reviewable_files(candidate_files, cur_ignore)
    if not reviewable_files:
        vlog(args.verbose, f"candidate files: {len(candidate_files)}, reviewable: 0")
        print("error: nothing to review", file=sys.stderr)
        print(f"hint: {_nothing_to_review_hint(args, candidate_files)}", file=sys.stderr)
        return ERROR, reviewable_files, "empty"
    if args.fix:
        fixed = 0
        try:
            for file_path in reviewable_files:
                fixed += fix_bare_except(file_path)
                fixed += fix_mutable_default_args(file_path)
        except (OSError, UnicodeDecodeError, tokenize.TokenError) as exc:
            print(f"error: could not apply fixes: {exc}", file=sys.stderr)
            return ERROR, reviewable_files, "fix error"
        if fixed:
            vlog(args.verbose, f"fixed {fixed} bare except clause(s)")
    if not args.not_git and not args.all_files and not args.changed:
        ranges = get_changed_line_ranges(reviewable_files, staged=args.staged)
    else:
        ranges = None
    cfg_label = config.get("_config_path") or "defaults (no avouch.toml)"
    vlog(args.verbose, f"config: {cfg_label}, {len(cur_ignore)} ignore path(s)")
    if args.verbose and cur_ignore:
        vlog(True, f"ignore paths: {', '.join(cur_ignore)}")
    file_reports = []
    functions_reports = []
    class_reports = []
    workers = _worker_count(len(reviewable_files))
    if workers == 1:
        for file_path in reviewable_files:
            vlog(args.verbose, f"analyzing {file_path}")
            functions, files, classes = analyze_file(file_path, limits, rules)
            functions_reports.extend(functions)
            file_reports.extend(files)
            class_reports.extend(classes)
    else:
        for file_path in reviewable_files:
            vlog(args.verbose, f"analyzing {file_path}")
        payloads = [(p, limits, rules) for p in reviewable_files]
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            for file_path, (functions, files, classes) in zip(reviewable_files, ex.map(_parallel_target, payloads)):
                vlog(args.verbose, f"analyzed {file_path}: {len(functions)} functions, {len(classes)} classes, {files[0]['lines']} lines")
                functions_reports.extend(functions)
                file_reports.extend(files)
                class_reports.extend(classes)
    if ranges is not None:
        functions_reports, file_reports, class_reports = _filter_changed_reports(functions_reports, file_reports, class_reports, ranges)
    suppressed = 0
    if not args.no_baseline:
        try:
            baseline_set = load_baseline()
        except ValueError as exc:
            print(f"error: invalid baseline: {exc}", file=sys.stderr)
            return ERROR, reviewable_files, "baseline error"
        if baseline_set is not None:
            functions_reports, file_reports, class_reports, suppressed = filter_reports(functions_reports, file_reports, class_reports, baseline_set)
            if args.verbose and suppressed:
                vlog(True, f"suppressed {suppressed} finding(s) by baseline")
    if not args.quiet:
        if args.changed:
            try:
                render_diff_view(reviewable_files, functions_reports, file_reports, class_reports)
            except Exception:
                render_diff_view(reviewable_files)
        else:
            generate_report(functions_reports, file_reports, class_reports, suppressed)
    reports = class_reports + functions_reports + file_reports
    exit_code = VIOLATIONS_FOUND if any(report["issues"] for report in reports) else SUCCESS
    vlog(args.verbose, f"exit code: {exit_code}")
    return exit_code, reviewable_files, "ok"


def _run_watch(args, ignore_paths, selected_rules, ignored_rules):
    import time
    interval = float(os.environ.get("AVOUCH_WATCH_INTERVAL", "0.5"))
    if interval < 0.1:
        interval = 0.1
    mode = "all" if args.all_files or args.not_git else ("staged" if args.staged else "changed")
    print(f"watching {mode} Python files \u00b7 interval {interval:.1f}s \u00b7 Ctrl+C to quit", file=sys.stderr)
    _, watched_files, _ = _run_single_review(args, ignore_paths, selected_rules, ignored_rules)
    prev_snap = _snapshot_files(watched_files)
    try:
        while True:
            time.sleep(interval)
            try:
                nxt = get_all_files_on_disk() if args.not_git else (get_all_files() if args.all_files else get_changed_files())
                cur_ignore = list(dict.fromkeys(load_config().get("ignore_paths", []) + (args.ignore_path or [])))
                nxt_rev = get_reviewable_files(nxt, cur_ignore)
                nxt_snap = _snapshot_files(nxt_rev)
            except Exception:
                continue
            if nxt_snap == prev_snap and set(nxt_rev) == set(watched_files):
                continue
            if sys.stdout.isatty():
                print("\033[2J\033[H", end="")
            ts = time.strftime("%H:%M:%S")
            diff = [k for k in set(list(nxt_snap.keys()) + list(prev_snap.keys())) if nxt_snap.get(k) != prev_snap.get(k)]
            added = set(nxt_rev) - set(watched_files)
            removed = set(watched_files) - set(nxt_rev)
            if diff:
                tag = ", ".join(diff[:2])
            elif added:
                tag = f"+{next(iter(added))}"
            elif removed:
                tag = f"-{next(iter(removed))}"
            else:
                tag = "file set changed"
            print(f"\u27f3 {ts} \u2014 change detected: {tag}", file=sys.stderr)
            _, watched_files, _ = _run_single_review(args, ignore_paths, selected_rules, ignored_rules)
            prev_snap = _snapshot_files(watched_files)
    except KeyboardInterrupt:
        print("\nWatch stopped.", file=sys.stderr)
        return SUCCESS


def main(argv=None):

    verbose = "--verbose" in (argv if argv is not None else sys.argv[1:])

    try:
        return _main(argv)
    except Exception as exc:
        print(f"error: internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return ERROR


def _main(argv=None):

    parser = argparse.ArgumentParser(
        prog="avouch",
        epilog=(
            "By default avouch reviews Python files changed vs Git HEAD, "
            "including untracked files. Exit codes: 0 = clean, "
            "1 = findings reported, 2 = error. Run 'avouch --docs' for the "
            "full documentation."
        ),
    )
    parser.add_argument("--docs", action="store_true", help="show built-in documentation and exit")
    parser.add_argument(
        "--version",
        action="version",
        version=f"avouch {AVOUCH_VERSION}",
        help="print the Avouch version and exit",
    )
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--format", choices=["github", "sarif"], help="output format for CI: github workflow commands or SARIF 2.1.0")
    parser.add_argument(
        "--ignore-path",
        action="append",
        metavar="PATH",
        help="exclude a repository-relative file or directory from the review; can be repeated",
    )
    parser.add_argument(
        "--select",
        action="append",
        metavar="RULES",
        help="review only the comma-separated rule IDs; can be repeated",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        metavar="RULES",
        help="skip the comma-separated rule IDs; can be repeated",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print step-by-step review details to stderr",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the normal report; errors and exit codes are unchanged",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="replace safe bare except clauses with except Exception before reviewing",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="watch Python files and re-run on change (polling, Ctrl+C to quit)",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--changed",
        action="store_true",
        help="show added and deleted lines of files changed vs Git HEAD instead of the findings report",
    )
    selection.add_argument(
        "--staged",
        action="store_true",
        help="review only files with staged Git changes",
    )
    selection.add_argument(
        "--all-files",
        action="store_true",
        help="review every eligible Python file in the repository",
    )
    selection.add_argument(
        "--list-changed",
        action="store_true",
        help="print each changed file path and exit",
    )
    selection.add_argument(
        "--display",
        metavar="FILE",
        help="display a file with syntax highlighting and paging",
    )
    parser.add_argument(
        "--not-git",
        action="store_true",
        help="analyze Python files without requiring a Git repository",
    )
    parser.add_argument("command", nargs="?", help="init, baseline, or rule")
    parser.add_argument("rule_id", nargs="?", help="rule ID for 'avouch rule' (e.g. SCR002)")
    parser.add_argument("--dry-run", action="store_true", help="print the avouch.toml that init would write without writing it")
    parser.add_argument("--no-baseline", action="store_true", help="disable baseline suppression")
    args = parser.parse_args(argv)

    try:
        selected_rules = _rule_filter_values(args.select)
        ignored_rules = _rule_filter_values(args.ignore)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("hint: use IDs such as SCR002,SCR017; run 'avouch rule' to list rules", file=sys.stderr)
        return ERROR

    if args.json and args.format:
        print("error: --json cannot be combined with --format", file=sys.stderr)
        print("hint: use one output format at a time", file=sys.stderr)
        return ERROR

    if args.format and args.changed:
        print("error: --format cannot be combined with --changed", file=sys.stderr)
        print("hint: --changed is a diff view, not a findings format", file=sys.stderr)
        return ERROR

    if args.watch and (args.json or args.format):
        print("error: --watch cannot be combined with --json or --format", file=sys.stderr)
        print("hint: --watch is an interactive human view; use plain avouch for JSON/SARIF", file=sys.stderr)
        return ERROR

    if args.watch and args.list_changed:
        print("error: --watch cannot be combined with --list-changed", file=sys.stderr)
        print("hint: --list-changed prints once and exits", file=sys.stderr)
        return ERROR

    if args.watch and args.display:
        print("error: --watch cannot be combined with --display", file=sys.stderr)
        print("hint: --display shows one file with a pager", file=sys.stderr)
        return ERROR

    if args.watch and args.command in ("init", "baseline", "rule"):
        print(f"error: --watch cannot be combined with '{args.command}'", file=sys.stderr)
        print("hint: run the command without --watch", file=sys.stderr)
        return ERROR

    if args.docs:
        render_docs()
        return SUCCESS

    if args.command == "rule":
        return _cmd_rule(args)

    if args.command == "init":
        return _cmd_init(args)

    if args.command == "baseline":
        return _cmd_baseline(args)

    if args.display:
        return _display_file(args.display)

    try:
        config = load_config()
    except ValueError as exc:
        print(f"error: invalid avouch.toml configuration: {exc}", file=sys.stderr)
        print(f"hint: check the [limits], [rules], and ignore_paths sections ({exc})", file=sys.stderr)
        return ERROR

    rules = config.get("rules", DEFAULT_RULES)
    if args.select:
        rules = {key: enabled and key in selected_rules for key, enabled in rules.items()}
    for key in ignored_rules:
        if key in rules:
            rules[key] = False
    limits = config.get("limits", DEFAULT_LIMITS)
    ignore_paths = config.get("ignore_paths", []) + (args.ignore_path or [])
    ignore_paths = list(dict.fromkeys(ignore_paths))

    if not args.not_git and not is_gitrepo():
        print("error: no Git repository found", file=sys.stderr)
        print(
            "hint: run Avouch from inside a Git repository, or use --not-git to review files without Git",
            file=sys.stderr,
        )
        return ERROR

    if args.not_git and (args.changed or args.staged or args.list_changed):
        if args.list_changed:
            print(
                "error: --not-git cannot be combined with --changed, --staged, or --list-changed",
                file=sys.stderr,
            )
            print(
                "hint: --changed, --staged, and --list-changed compare against Git history, which --not-git bypasses",
                file=sys.stderr,
            )
        else:
            print(
                "error: --not-git cannot be combined with --changed or --staged",
                file=sys.stderr,
            )
            print(
                "hint: --changed and --staged compare against Git history, which --not-git bypasses",
                file=sys.stderr,
            )
        return ERROR

    if args.list_changed:
        if not is_gitrepo():
            print("error: no Git repository found", file=sys.stderr)
            print(
                "hint: run Avouch from inside a Git repository to list changed files",
                file=sys.stderr,
            )
            return ERROR

        candidate_files = get_changed_files()
        reviewable_files = get_reviewable_files(candidate_files, ignore_paths)

        if not reviewable_files:
            print("No changed files.")
            return SUCCESS

        for file_path in reviewable_files:
            print(file_path)
        return SUCCESS

    if args.watch:
        return _run_watch(args, ignore_paths, selected_rules, ignored_rules)

    if args.not_git:
        candidate_files = get_all_files_on_disk()
    elif args.all_files:
        candidate_files = get_all_files()
    elif args.staged:
        candidate_files = get_staged_files()
    else:
        candidate_files = get_changed_files()

    reviewable_files = get_reviewable_files(candidate_files, ignore_paths)

    if not reviewable_files:
        vlog(args.verbose, f"candidate files: {len(candidate_files)}, reviewable: 0")
        print("error: nothing to review", file=sys.stderr)
        print(f"hint: {_nothing_to_review_hint(args, candidate_files)}", file=sys.stderr)
        return ERROR

    if args.fix:
        fixed = 0
        try:
            for file_path in reviewable_files:
                fixed += fix_bare_except(file_path)
                fixed += fix_mutable_default_args(file_path)
        except (OSError, UnicodeDecodeError, tokenize.TokenError) as exc:
            print(f"error: could not apply fixes: {exc}", file=sys.stderr)
            return ERROR
        if fixed:
            vlog(args.verbose, f"fixed {fixed} bare except clause(s)")

    if not args.not_git and not args.all_files and not args.changed:
        ranges = get_changed_line_ranges(reviewable_files, staged=args.staged)
    else:
        ranges = None

    cfg_label = config.get("_config_path") or "defaults (no avouch.toml)"
    vlog(
        args.verbose,
        f"config: {cfg_label}, "
        f"{len(ignore_paths)} ignore path(s)", 
    )
    if args.verbose and ignore_paths:
        vlog(True, f"ignore paths: {', '.join(ignore_paths)}")
    if args.not_git:
        vlog(args.verbose, "review mode: all Python files on disk (--not-git)")
        vlog(
            args.verbose,
            f"reviewing {len(reviewable_files)} of {len(candidate_files)} "
            f"Python file{'s' if len(reviewable_files) != 1 else ''}",
        )
    elif args.all_files:
        vlog(args.verbose, "review mode: all repository files (git ls-files)")
        vlog(
            args.verbose,
            f"reviewing {len(reviewable_files)} of {len(candidate_files)} "
            f"repository file{'s' if len(reviewable_files) != 1 else ''}",
        )
    elif args.staged:
        vlog(args.verbose, "review mode: staged files (git diff --cached --name-only)")
        vlog(
            args.verbose,
            f"reviewing {len(reviewable_files)} of {len(candidate_files)} "
            f"staged file{'s' if len(reviewable_files) != 1 else ''}",
        )
    else:
        vlog(
            args.verbose,
            "review mode: changed files vs HEAD (git diff HEAD --name-only) + untracked files",
        )
        vlog(
            args.verbose,
            f"reviewing {len(reviewable_files)} of {len(candidate_files)} "
            f"changed file{'s' if len(reviewable_files) != 1 else ''}",
        )
    if args.verbose:
        names = ", ".join(reviewable_files[:10])

        if len(reviewable_files) > 10:
            names += ", ..."

        vlog(True, f"review set: {names}")

        skipped = [file for file in candidate_files if file not in reviewable_files]

        if skipped:
            names = ", ".join(skipped[:10])

            if len(skipped) > 10:
                names += ", ..."

            vlog(True, f"skipped {len(skipped)} non-reviewable file(s): {names}")

    file_reports = []
    functions_reports = []
    class_reports = []

    workers = _worker_count(len(reviewable_files))
    if workers == 1:
        for file_path in reviewable_files:
            vlog(args.verbose, f"analyzing {file_path}")
            functions, files, classes = analyze_file(file_path, limits, rules)
            vlog(
                args.verbose,
                f"analyzed {file_path}: {len(functions)} functions, "
                f"{len(classes)} classes, {files[0]['lines']} lines", 
            )
            functions_reports.extend(functions)
            file_reports.extend(files)
            class_reports.extend(classes)

    else:
        for file_path in reviewable_files:
            vlog(args.verbose, f"analyzing {file_path}")
        payloads = [(p, limits, rules) for p in reviewable_files]
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            for file_path, (functions, files, classes) in zip(reviewable_files, ex.map(_parallel_target, payloads)):
                vlog(
                    args.verbose,
                    f"analyzed {file_path}: {len(functions)} functions, "
                    f"{len(classes)} classes, {files[0]['lines']} lines", 
                )
                functions_reports.extend(functions)
                file_reports.extend(files)
                class_reports.extend(classes)

    if ranges is not None:
        functions_reports, file_reports, class_reports = _filter_changed_reports(
            functions_reports, file_reports, class_reports, ranges
        )

    suppressed = 0
    if not args.no_baseline:
        try:
            baseline_set = load_baseline()
        except ValueError as exc:
            print(f"error: invalid baseline: {exc}", file=sys.stderr)
            return ERROR
        if baseline_set is not None:
            functions_reports, file_reports, class_reports, suppressed = filter_reports(
                functions_reports, file_reports, class_reports, baseline_set
            )
            if args.verbose and suppressed:
                vlog(True, f"suppressed {suppressed} finding(s) by baseline")

    if args.json:
        render_json(functions_reports, file_reports, class_reports)
    elif args.format == "github":
        render_github(functions_reports, file_reports, class_reports)
    elif args.format == "sarif":
        render_sarif(functions_reports, file_reports, class_reports)
    elif not args.quiet:
        if args.changed:
            try:
                render_diff_view(reviewable_files, functions_reports, file_reports, class_reports)
            except Exception:
                render_diff_view(reviewable_files)
        else:
            generate_report(functions_reports, file_reports, class_reports, suppressed)

    reports = class_reports + functions_reports + file_reports

    if args.verbose:
        findings = [issue for report in reports for issue in report["issues"]]
        errors = sum(1 for issue in findings if issue["severity"] == "ERROR")
        warnings = len(findings) - errors
        files_with_findings = len(
            {
                report["file"] if "file" in report else report["name"]
                for report in reports
                if report["issues"]
            }
        )

        vlog(
            True,
            f"findings: {len(findings)} ({warnings} warning{'s' if warnings != 1 else ''}, "
            f"{errors} error{'s' if errors != 1 else ''}) in "
            f"{files_with_findings} file{'s' if files_with_findings != 1 else ''}",
        )

    exit_code = VIOLATIONS_FOUND if any(report["issues"] for report in reports) else SUCCESS

    vlog(args.verbose, f"exit code: {exit_code}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

def _serialize_config(config):

    sections = []

    if config.get("ignore_paths"):
        sections.append(f"ignore_paths = {config['ignore_paths']!s}")

    limits_lines = ["[limits]"] + [f"{k} = {v}" for k, v in config["limits"].items()]

    sections.append("\n".join(limits_lines))

    if config.get("rules"):
        rules_lines = ["[rules]"] + [f"{k} = {str(v).lower()}" for k, v in config["rules"].items()]

        sections.append("\n".join(rules_lines))

    return "\n\n".join(sections) + "\n"


def _cmd_init(args):

    if args.changed or args.staged or args.all_files or args.not_git:
        print(
            "error: init cannot be combined with --changed, --staged, --all-files, or --not-git",
            file=sys.stderr,
        )
        return ERROR

    try:
        config = load_config()
    except ValueError as exc:
        print(f"error: invalid avouch.toml configuration: {exc}", file=sys.stderr)
        print(f"hint: check the [limits], [rules], and ignore_paths sections ({exc})", file=sys.stderr)
        return ERROR

    files = get_reviewable_files(get_all_files_on_disk(), config["ignore_paths"])

    if not files:
        print("error: nothing to measure", file=sys.stderr)
        print("hint: avouch init measures every Python file under the current directory", file=sys.stderr)
        return ERROR

    maxima = measure_maxima(files, config["rules"])

    limits = {
        key: (maxima[key] + 1 if maxima[key] > 0 else config["limits"][key])
        for key in DEFAULT_LIMITS
    }

    existing = {}

    if Path("avouch.toml").exists():
        with open("avouch.toml", "rb") as file:
            existing = tomllib.load(file)

    existing["limits"] = limits

    serialized = _serialize_config(existing)

    if args.dry_run:
        print(serialized, end="")
        return SUCCESS

    Path("avouch.toml").write_text(serialized, encoding="utf-8")

    print(f"avouch.toml written: measured {len(limits)} maxima across {len(files)} files")

    return SUCCESS


def _cmd_baseline(args):

    if args.changed or args.staged or args.all_files or args.not_git:
        print(
            "error: baseline cannot be combined with --changed, --staged, --all-files, or --not-git",
            file=sys.stderr,
        )
        return ERROR

    try:
        config = load_config()
    except ValueError as exc:
        print(f"error: invalid avouch.toml configuration: {exc}", file=sys.stderr)
        print(f"hint: check the [limits], [rules], and ignore_paths sections ({exc})", file=sys.stderr)
        return ERROR

    files = get_reviewable_files(get_all_files_on_disk(), config["ignore_paths"])

    if not files:
        print("error: nothing to baseline", file=sys.stderr)
        print("hint: no reviewable .py files found on disk", file=sys.stderr)
        return ERROR

    rules = config.get("rules", DEFAULT_RULES)
    limits = config.get("limits", DEFAULT_LIMITS)

    file_reports = []
    functions_reports = []
    class_reports = []

    for file_path in files:
        functions, f_reports, classes = analyze_file(file_path, limits, rules)
        functions_reports.extend(functions)
        file_reports.extend(f_reports)
        class_reports.extend(classes)

    count = write_baseline(functions_reports, file_reports, class_reports)

    print(f"baseline written: {count} finding(s) across {len(files)} files")

    return SUCCESS


def _cmd_rule(args):

    from avouch.utility.docs import RULES, render_rule

    if args.rule_id is None:
        for rid in sorted(RULES):
            print(f"{rid}  {RULES[rid]['name']}")
        return SUCCESS

    rid = args.rule_id.upper()
    text = render_rule(rid)
    if text is None:
        print(f"error: unknown rule '{args.rule_id}'", file=sys.stderr)
        print("hint: try 'avouch --docs' or 'avouch rule SCR013'", file=sys.stderr)
        return ERROR
    print(text)
    return SUCCESS
