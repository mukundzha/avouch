import ast
import subprocess
from pathlib import Path

PARAMETER_LIMIT = 5
NESTING_LIMIT = 4
FILE_LINE_LIMIT = 400
CLASS_LINE_LIMIT = 200


def is_gitrepo() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_reviewable_files(files: list[str]) -> list[Path]:
    return [Path(path) for path in files if path.endswith(".py")]


def read_file(file_path: Path) -> str | None:
    try:
        with file_path.open("r", encoding="utf-8") as file:
            return file.read()
    except OSError:
        print(f"Couldn't read {file_path}")
        return None


def get_depth(node: ast.AST, depth: int = 0) -> int:
    max_depth = depth

    for child in ast.iter_child_nodes(node):
        next_depth = depth + 1 if isinstance(child, (ast.For, ast.If, ast.While)) else depth
        max_depth = max(max_depth, get_depth(child, next_depth))

    return max_depth


def analyze_file(file_path: Path) -> tuple[dict, list[dict], list[dict]]:
    source_code = read_file(file_path)
    if source_code is None:
        return {}, [], []

    try:
        parsed = ast.parse(source_code)
    except SyntaxError:
        print(f"Python syntax error in {file_path}")
        return {}, [], []

    function_reports = []
    class_reports = []

    for node in ast.walk(parsed):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            issues = []
            line_count = node.end_lineno - node.lineno + 1
            param_count = len(node.args.args)
            nesting_depth = get_depth(node)

            if param_count > PARAMETER_LIMIT:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Too many parameters ({param_count}/{PARAMETER_LIMIT})",
                    }
                )

            if nesting_depth > NESTING_LIMIT:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Nesting too deep ({nesting_depth}/{NESTING_LIMIT})",
                    }
                )

            function_reports.append(
                {
                    "name": node.name,
                    "lines": line_count,
                    "parameters": param_count,
                    "nesting_depth": nesting_depth,
                    "issues": issues,
                }
            )

        elif isinstance(node, ast.ClassDef):
            issues = []
            class_line_count = node.end_lineno - node.lineno + 1

            if class_line_count > CLASS_LINE_LIMIT:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Class too large ({class_line_count}/{CLASS_LINE_LIMIT})",
                    }
                )

            class_reports.append(
                {"name": node.name, "lines": class_line_count, "issues": issues}
            )

    file_line_count = len(source_code.splitlines())
    file_issues = []

    if file_line_count > FILE_LINE_LIMIT:
        file_issues.append(
            {
                "severity": "WARNING",
                "message": f"File too large ({file_line_count}/{FILE_LINE_LIMIT})",
            }
        )

    file_report = {
        "name": str(file_path),
        "lines": file_line_count,
        "issues": file_issues,
    }

    return file_report, function_reports, class_reports


def generate_report(function_reports: list[dict], file_reports: list[dict], class_reports: list[dict]):
    print("=" * 50)
    print("SCRUT REPORT")
    print("=" * 50)

    total_issues = sum(len(report["issues"]) for report in file_reports + function_reports + class_reports)

    print("\nFILE")
    print("-" * 50)
    for report in file_reports:
        print(f"Name   : {report['name']}")
        print(f"Lines  : {report['lines']}")
        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  [{issue['severity']}] {issue['message']}")
        else:
            print("Issues: None")

    print("\nFUNCTIONS")
    print("-" * 50)
    for index, report in enumerate(function_reports, start=1):
        print(f"\nFunction {index}: {report['name']}")
        print(f"Lines         : {report['lines']}")
        print(f"Parameters    : {report['parameters']}")
        print(f"Nesting Depth : {report['nesting_depth']}")
        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  [{issue['severity']}] {issue['message']}")
        else:
            print("Issues: None")

    print("\nCLASSES")
    print("-" * 50)
    if class_reports:
        for report in class_reports:
            print(f"\nClass: {report['name']}")
            print(f"Lines: {report['lines']}")
            if report["issues"]:
                print("Issues:")
                for issue in report["issues"]:
                    print(f"  [{issue['severity']}] {issue['message']}")
            else:
                print("Issues: None")
    else:
        print("No classes found.")

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Functions Reviewed : {len(function_reports)}")
    print(f"Classes Reviewed   : {len(class_reports)}")
    print(f"Files Reviewed     : {len(file_reports)}")
    print(f"Issues Found       : {total_issues}")
    print("=" * 50)


def main():
    if not is_gitrepo():
        print("Not inside a Git repository.")
        return

    changed_files = get_changed_files()
    reviewable_files = get_reviewable_files(changed_files)

    if not reviewable_files:
        print("No Python files to review.")
        return

    file_reports = []
    function_reports = []
    class_reports = []

    for file_path in reviewable_files:
        file_report, functions, classes = analyze_file(file_path)
        if file_report:
            file_reports.append(file_report)
            function_reports.extend(functions)
            class_reports.extend(classes)

    if not file_reports:
        print("No valid Python files to review.")
        return

    generate_report(function_reports, file_reports, class_reports)


if __name__ == "__main__":
    main()