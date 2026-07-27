import subprocess
import ast


def is_gitrepo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True
    else:
        return False
    

def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True
    )

    print("\nChanged File(s):\n" + result.stdout)
    return result.stdout.splitlines()


def get_reviewable_files(files):
    reviewable = []

    for file in files:
        if file.endswith(".py"):
            reviewable.append(file)

    print("Reviewable File(s):" , reviewable)
    return reviewable


def read_file(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    return content


is_gitrepo()
changed_files = get_changed_files()
reviewable_files = get_reviewable_files(changed_files)

source_code = read_file(reviewable_files[0])

parsed = ast.parse(source_code)

for node in ast.walk(parsed):
    if isinstance(node, ast.FunctionDef):
        print(f"\nFunction: {node.name}")

        lineno = node.lineno
        end_lineno = node.end_lineno
        line_count = end_lineno - lineno + 1

        print(f"Lines: {line_count}")

        param_count = len(node.args.args)
        print(f"Parameters: {param_count}")

        for parameter in node.args.args:
            print(f"  - {parameter.arg}")

        if param_count <= 5:
         print("Parameter Count: OK")
        else:
         limit = 5
         print(f"Issue: Too many parameters ({param_count}/{limit})")