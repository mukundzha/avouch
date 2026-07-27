import subprocess
import ast

PARAMETER_LIMIT = 5
NESTING_LIMIT = 3

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
def get_depth(node, depth=0):
    max_depth = depth

    for child in ast.iter_child_nodes(node):

        if isinstance(child, (ast.For, ast.If, ast.While)):
            max_depth = max(max_depth, get_depth(child, depth + 1))
        else:
            max_depth = max(max_depth, get_depth(child, depth))

    return max_depth

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
         print(f"Issue: Too many parameters ({PARAMETER_LIMIT}/{limit})")

        nesting_limit = 3
        nesting_depth = get_depth(node)
        
        print(f"Nesting Depth: {nesting_depth}")
        
        if nesting_depth > nesting_limit:
            print(f"Issue: Nesting too deep ({nesting_depth}/{NESTING_LIMIT})")
        else:
            print("Nesting Depth: OK")

        FILE_LINE_LIMIT = 350
        file_line_count = len(source_code.splitlines())
        print(f"File Lines: {file_line_count}")
        if file_line_count > FILE_LINE_LIMIT:
            print("Issue: File too large ({file_line_count}/{FILE_LINE_LIMIT})")
        else:
            print("File Size: OK")


        print("----------------------------")
