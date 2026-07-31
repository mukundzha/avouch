import subprocess
from pathlib import Path
import ast
from scrut.config.loader import load_config
from scrut.config.default import DEFAULT_LIMITS


def is_gitrepo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
    )
    return result.returncode == 0


def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "HEAD", "--name-only"], capture_output=True, text=True
    )
    return result.stdout.splitlines()


def get_reviewable_files(files):
    reviewable = []

    for file in files:
        path = Path(file)

        if path.suffix == ".py" and path.exists():
            reviewable.append(str(path))

    return reviewable


def read_file(file_path):

    try:
        with open(file_path, "r") as file:
            return file.read()
    except OSError:
        print(f"Couldn't read {file_path}")
        return None


def get_depth(node, depth=0):
    max_depth = depth

    for child in ast.iter_child_nodes(node):

        if isinstance(child, (ast.For, ast.If, ast.While)):
            max_depth = max(max_depth, get_depth(child, depth + 1))
        else:
            max_depth = max(max_depth, get_depth(child, depth))

    return max_depth


def analyze_file(file_path, limits):
    source_code = read_file(file_path)

    if source_code is None:
        return (
            [],
            [
                {
                    "name": file_path,
                    "lines": 0,
                    "issues": [{"severity": "ERROR", "message": "Could not read file"}],
                }
            ],
            [],
        )

    try:
        parsed = ast.parse(source_code)
    except SyntaxError:
        return (
            [],
            [
                {
                    "name": file_path,
                    "lines": 0,
                    "issues": [{"severity": "ERROR", "message": "Python syntax error"}],
                }
            ],
            [],
        )

    funcs = []
    cls = []

    for node in ast.walk(parsed):
        if isinstance(node, ast.FunctionDef):

            issues = []
            line_count = node.end_lineno - node.lineno + 1
            param_count = len(node.args.args)
            nesting_depth = get_depth(node)

            if line_count > limits["max_function_lines"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Function too long ({line_count}/{limits['max_function_lines']})",
                    }
                )

            if param_count > limits["max_parameters"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Too many parameters ({param_count}/{limits['max_parameters']})",
                    }
                )

            if nesting_depth > limits["max_nesting"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Nesting too deep ({nesting_depth}/{limits['max_nesting']})",
                    }
                )

            funcs.append(
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

            if class_line_count > limits["max_class_lines"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Class too large ({class_line_count}/{limits['max_class_lines']})",
                    }
                )

            cls.append({"name": node.name, "lines": class_line_count, "issues": issues})

    file_line_count = len(source_code.splitlines())
    file_issues = []

    if file_line_count > limits["max_file_lines"]:
        file_issues.append(
            {
                "severity": "WARNING",
                "message": f"File too large ({file_line_count}/{limits['max_file_lines']})",
            }
        )

    return (
        funcs,
        [{"name": file_path, "lines": file_line_count, "issues": file_issues}],
        cls,
    )


def generate_report(function_reports, file_reports, class_reports):

    print("SCRUT REPORT")
    print("=" * 50)
    print("=" * 50)

    total_issues = 0

    print("\nFILE")
    print("-" * 50)

    for report in file_reports:
        print(f"Name   : {report['name']}")
        print(f"Lines  : {report['lines']}")

        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  [{issue['severity']}] {issue['message']}")
            total_issues += len(report["issues"])
            print("")
            # print("==============================")
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
            total_issues += len(report["issues"])
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
                total_issues += len(report["issues"])
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

    config = load_config()
    limits = config.get("limits", DEFAULT_LIMITS)

    if not is_gitrepo():
        print("Not inside a Git repository.")
        return

    changed_files = get_changed_files()
    reviewable_files = get_reviewable_files(changed_files)

    if not reviewable_files:
        print("No Python files to review.")
        return

    file_reports = []
    functions_reports = []
    class_reports = []

    for file_path in reviewable_files:
        functions, files, classes = analyze_file(file_path, limits)
        functions_reports.extend(functions)
        file_reports.extend(files)
        class_reports.extend(classes)

    generate_report(functions_reports, file_reports, class_reports)


if __name__ == "__main__":
    main()
