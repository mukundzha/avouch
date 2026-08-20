import argparse
import importlib.metadata
import sys
import tomllib
import traceback
from pathlib import Path

from avouch.config.loader import DEFAULT_RULES, load_config
from avouch.config.default import DEFAULT_LIMITS
from avouch.analyzer import analyze_file
from avouch.report import generate_report, render_diff_view, render_json, vlog
from avouch.utility.docs import render_docs
from avouch.git import is_gitrepo, get_changed_files, get_staged_files, get_all_files, get_all_files_on_disk, get_reviewable_files
from avouch.utility.measure import measure_maxima

SUCCESS = 0
VIOLATIONS_FOUND = 1
ERROR = 2

try:
    AVOUCH_VERSION = importlib.metadata.version("avouch")
except importlib.metadata.PackageNotFoundError:
    AVOUCH_VERSION = "0.3.2"


def _nothing_to_review_hint(args, candidate_files):

    if args.not_git:
        return "no reviewable .py files found on disk"
    if not candidate_files and not args.staged:
        return "nothing changed vs HEAD (CI checkouts are clean); use --all-files for a full review"
    return "change or stage .py files, or use --all-files"


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
    parser.add_argument(
        "--not-git",
        action="store_true",
        help="analyze Python files without requiring a Git repository",
    )
    parser.add_argument("init", nargs="?", const="init", help="bootstrap avouch.toml from the current repository")
    parser.add_argument("--dry-run", action="store_true", help="print the avouch.toml that init would write without writing it")
    args = parser.parse_args(argv)

    if args.docs:
        render_docs()
        return SUCCESS

    if args.init:
        return _cmd_init(args)

    try:
        config = load_config()
    except ValueError as exc:
        print(f"error: invalid avouch.toml configuration: {exc}", file=sys.stderr)
        print("hint: check the [limits], [rules], and ignore_paths sections", file=sys.stderr)
        return ERROR

    rules = config.get("rules", DEFAULT_RULES)
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

    if args.not_git and (args.changed or args.staged):
        print(
            "error: --not-git cannot be combined with --changed or --staged",
            file=sys.stderr,
        )
        print(
            "hint: --changed and --staged compare against Git history, which --not-git bypasses",
            file=sys.stderr,
        )
        return ERROR

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

    vlog(
        args.verbose,
        f"config: {'avouch.toml' if Path('avouch.toml').exists() else 'defaults (no avouch.toml)'}, "
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
        print("hint: check the [limits], [rules], and ignore_paths sections", file=sys.stderr)
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
