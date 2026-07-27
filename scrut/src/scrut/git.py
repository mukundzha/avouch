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


is_gitrepo()

changed_files = get_changed_files()

reviewable_files = get_reviewable_files(changed_files)

source_code = read_file(reviewable_files[0])

parsed = ast.parse(source_code)

for node in ast.walk(parsed):

    if isinstance(node, ast.FunctionDef):

        lineno = node.lineno
        end_lineno = node.end_lineno
        line_count = end_lineno - lineno + 1

        param_count = len(node.args.args)

        for parameter in node.args.args:
            pass

        if param_count <= PARAMETER_LIMIT:
            pass
        else:
            pass

        nesting_depth = get_depth(node)

        if nesting_depth > NESTING_LIMIT:
            pass
        else:
            pass

        file_line_count = len(source_code.splitlines())

        if file_line_count > FILE_LINE_LIMIT:
            pass
        else:
            pass

    if isinstance(node, ast.ClassDef):

        class_start = node.lineno
        class_end = node.end_lineno
        class_line_count = class_end - class_start + 1

        if class_line_count > CLASS_LINE_LIMIT:
            pass
        else:
            pass

