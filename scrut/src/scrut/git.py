import subprocess
import ast

PARAMETER_LIMIT = 5
NESTING_LIMIT = 3
FILE_LINE_LIMIT = 350
CLASS_LINE_LIMIT = 200


def is_gitrepo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True
    )
    return result.stdout.splitlines()


def get_reviewable_files(files):
    reviewable = []
    for file in files:
        if file.endswith(".py"):
            reviewable.append(file)
    return reviewable


def read_file(file_path):
    with open(file_path, "r") as file:
        return file.read()


def get_depth(node, depth=0):
    max_depth = depth

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.For, ast.If, ast.While)):
            max_depth = max(max_depth, get_depth(child, depth + 1))
        else:
            max_depth = max(max_depth, get_depth(child, depth))

    return max_depth


changed_files = get_changed_files()
reviewable_files = get_reviewable_files(changed_files)

source_code = read_file(reviewable_files[0])
parsed = ast.parse(source_code)

file_reports = []
functions_reports = []
class_reports = []

for node in ast.walk(parsed):

    if isinstance(node, ast.FunctionDef):

        issues = []

        line_count = node.end_lineno - node.lineno + 1
        param_count = len(node.args.args)
        nesting_depth = get_depth(node)

        if param_count > PARAMETER_LIMIT:
            issues.append(f"Too many parameters ({param_count}/{PARAMETER_LIMIT})")

        if nesting_depth > NESTING_LIMIT:
            issues.append(f"Nesting too deep ({nesting_depth}/{NESTING_LIMIT})")

        functions_reports.append({
            "name": node.name,
            "lines": line_count,
            "parameters": param_count,
            "nesting_depth": nesting_depth,
            "issues": issues
        })

    if isinstance(node, ast.ClassDef):

        issues = []

        class_line_count = node.end_lineno - node.lineno + 1

        if class_line_count > CLASS_LINE_LIMIT:
            issues.append(
                f"Class too large ({class_line_count}/{CLASS_LINE_LIMIT})"
            )

        class_reports.append({
            "name": node.name,
            "lines": class_line_count,
            "issues": issues
        })

file_line_count = len(source_code.splitlines())

file_issues = []

if file_line_count > FILE_LINE_LIMIT:
    file_issues.append(
        f"File too large ({file_line_count}/{FILE_LINE_LIMIT})"
    )

file_reports.append({
    "name": reviewable_files[0],
    "lines": file_line_count,
    "issues": file_issues
})


def generate_report(function_reports, file_reports, class_reports):

    print("=" * 50)
    print("SCRUT REPORT")
    print("=" * 50)

    print("\nFILE")
    print("-" * 50)

    for report in file_reports:
        print(f"Name   : {report['name']}")
        print(f"Lines  : {report['lines']}")
        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  - {issue}")
        else:
            print("Issues: None")

    print("\nFUNCTIONS")
    print("-" * 50)

    total_issues = 0

    for index, report in enumerate(function_reports, start=1):
        print(f"\nFunction {index}: {report['name']}")
        print(f"Lines         : {report['lines']}")
        print(f"Parameters    : {report['parameters']}")
        print(f"Nesting Depth : {report['nesting_depth']}")

        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  - {issue}")
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
                    print(f"  - {issue}")
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
    print(f"Issues Found       : {total_issues}")
    print("=" * 50)


generate_report(functions_reports, file_reports, class_reports)
