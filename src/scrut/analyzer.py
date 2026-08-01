
import ast

BLOCK_NODES = (
    ast.If,
    ast.For,
    ast.While,
    ast.AsyncFor,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)

def read_file(file_path):

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except OSError:
        print(f"Couldn't read {file_path}")
        return None


def get_depth(node, depth=0):
    max_depth = depth

    for child in ast.iter_child_nodes(node):

        if isinstance(child, BLOCK_NODES):
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
