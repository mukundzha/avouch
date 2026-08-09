import argparse

from scrut.config.loader import DEFAULT_RULES, load_config
from scrut.config.default import DEFAULT_LIMITS
from scrut.analyzer import analyze_file
from scrut.report import generate_report, render_json
from scrut.git import is_gitrepo, get_changed_files, get_reviewable_files

SUCCESS = 0
VIOLATIONS_FOUND = 1
ERROR = 2


def main(argv=None):

    parser = argparse.ArgumentParser(prog="scrut")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument(
        "--ignore-path",
        action="append",
        metavar="PATH",
        help="exclude a repository-relative file or directory from the review; can be repeated",
    )
    args = parser.parse_args(argv)

    config = load_config()
    rules = config.get("rules", DEFAULT_RULES)
    limits = config.get("limits", DEFAULT_LIMITS)
    ignore_paths = config.get("ignore_paths", []) + (args.ignore_path or [])
    ignore_paths = list(dict.fromkeys(ignore_paths))

    if not is_gitrepo():
        print("Not inside a Git repository.")
        return ERROR

    changed_files = get_changed_files()
    reviewable_files = get_reviewable_files(changed_files, ignore_paths)

    if not reviewable_files:
        print("No Python files to review.")
        return ERROR

    file_reports = []
    functions_reports = []
    class_reports = []

    for file_path in reviewable_files:
        functions, files, classes = analyze_file(file_path, limits, rules)
        functions_reports.extend(functions)
        file_reports.extend(files)
        class_reports.extend(classes)

    if args.json:
        render_json(functions_reports, file_reports, class_reports)
    else:
        generate_report(functions_reports, file_reports, class_reports)

    reports = class_reports + functions_reports + file_reports

    if any(report["issues"] for report in reports):
        return VIOLATIONS_FOUND

    return SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())