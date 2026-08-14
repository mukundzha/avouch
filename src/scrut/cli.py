import argparse
import sys
import traceback
from pathlib import Path

from scrut.config.loader import DEFAULT_RULES, load_config
from scrut.config.default import DEFAULT_LIMITS
from scrut.analyzer import analyze_file
from scrut.report import generate_report, render_diff_view, render_json, vlog
from scrut.utility.docs import DOCS
from scrut.git import is_gitrepo, get_changed_files, get_staged_files, get_all_files, get_reviewable_files

SUCCESS = 0
VIOLATIONS_FOUND = 1
ERROR = 2


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
        prog="scrut",
        epilog=(
            "By default scrut reviews Python files changed vs Git HEAD, "
            "including untracked files. Exit codes: 0 = clean, "
            "1 = findings reported, 2 = error. Run 'scrut --docs' for the "
            "full documentation."
        ),
    )
    parser.add_argument("--docs", action="store_true", help="show built-in documentation and exit")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument(
        "--ignore-path",
        action="append",
        metavar="PATH",
        help="exclude a repository-relative file or directory from the review; can be repeated",
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
    args = parser.parse_args(argv)

    if args.docs:
        print(DOCS)
        return SUCCESS

    try:
        config = load_config()
    except ValueError as exc:
        print(f"error: invalid scrut.toml configuration: {exc}", file=sys.stderr)
        print("hint: check the [limits], [rules], and ignore_paths sections", file=sys.stderr)
        return ERROR

    rules = config.get("rules", DEFAULT_RULES)
    limits = config.get("limits", DEFAULT_LIMITS)
    ignore_paths = config.get("ignore_paths", []) + (args.ignore_path or [])
    ignore_paths = list(dict.fromkeys(ignore_paths))

    if not is_gitrepo():
        print("error: no Git repository found", file=sys.stderr)
        print("hint: run Scrut from inside a Git repository", file=sys.stderr)
        return ERROR

    if args.all_files:
        candidate_files = get_all_files()
    elif args.staged:
        candidate_files = get_staged_files()
    else:
        candidate_files = get_changed_files()

    reviewable_files = get_reviewable_files(candidate_files, ignore_paths)

    if not reviewable_files:
        vlog(args.verbose, f"candidate files: {len(candidate_files)}, reviewable: 0")
        print("error: nothing to review", file=sys.stderr)
        print("hint: change or stage .py files, or use --all-files", file=sys.stderr)
        return ERROR

    vlog(
        args.verbose,
        f"config: {'scrut.toml' if Path('scrut.toml').exists() else 'defaults (no scrut.toml)'}, "
        f"{len(ignore_paths)} ignore path(s)",
    )
    if args.verbose and ignore_paths:
        vlog(True, f"ignore paths: {', '.join(ignore_paths)}")
    if args.all_files:
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

    if args.json:
        render_json(functions_reports, file_reports, class_reports)
    elif not args.quiet:
        if args.changed:
            render_diff_view(reviewable_files)
        else:
            generate_report(functions_reports, file_reports, class_reports)

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