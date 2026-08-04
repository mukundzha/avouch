from scrut.rules.complexity import calculate_complexity
from scrut.rules.boolean_complexity import analyze as analyze_boolean_complexity
from scrut.rules.detect_duplicateb import analyze as analyze_duplicateb 
from scrut.rules.bare_except import analyze as analyze_bare_except 
from scrut.rules.if_else_chain import analyze as analyze_if_else_chain
from scrut.rules.empty_except import analyze as analyze_empty_except 
from scrut.rules.detect_large_comprehensions import analyze as analyze_large_comprehensions
from scrut.rules.local_variables import analyze as analyze_local_variables
from scrut.rules.nested_function import analyze as analyze_nested_function
from scrut.rules.return_statements import analyze as analyze_return_statements
from scrut.rules.large_lambda import analyze as analyze_large_lambda

import ast

BLOCK_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
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

def analyze_file(file_path, limits, rules):
    
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
            complexity = calculate_complexity(node)

            if rules["max_function_lines"] and line_count > limits["max_function_lines"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Function too long ({line_count}/{limits['max_function_lines']}). Extract helper functions or split into smaller units.",
                    }
                )

            if rules["max_complexity"] and complexity > limits["max_complexity"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Function too complex ({complexity}/{limits['max_complexity']}). Reduce branching or extract nested logic into separate functions.",
                    }
                )

            if rules["max_boolean_conditions"]:
                issues.extend(analyze_boolean_complexity(node, limits))

            if rules["max_parameters"] and param_count > limits["max_parameters"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Too many parameters ({param_count}/{limits['max_parameters']}). Group related parameters into a data class or dictionary.",
                    }
                )

            if rules["empty_except"]:
                issues.extend(analyze_empty_except(node, limits))
            if rules["max_if_else_chain"]:
                issues.extend(analyze_if_else_chain(node, limits))
            if rules["max_lambda_nodes"]:
                issues.extend(analyze_large_lambda(node, limits))
            if rules["max_local_variables"]:
                issues.extend(analyze_local_variables(node, limits))

            if rules["max_nesting"] and nesting_depth > limits["max_nesting"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Nesting too deep ({nesting_depth}/{limits['max_nesting']}). Flatten control flow with early returns or guard clauses.",
                    }
                )

            funcs.append(
                {
                    "name": node.name,
                    "file": file_path,
                    "lines": line_count,
                    "parameters": param_count,
                    "nesting_depth": nesting_depth,
                    "issues": issues,
                }
            )

            if rules["detect_duplicateb"]:
                issues.extend(analyze_duplicateb(node, limits))
            if rules["max_large_comprehensions"]:
                issues.extend(analyze_large_comprehensions(node, limits))
            if rules["nested_function"]:
                issues.extend(analyze_nested_function(node, limits))
            if rules["max_return_statements"]:
                issues.extend(analyze_return_statements(node, limits))

        elif isinstance(node, ast.ClassDef):
            issues = []
            class_line_count = node.end_lineno - node.lineno + 1
            complexity = calculate_complexity(node)

            if rules["max_class_lines"] and class_line_count > limits["max_class_lines"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Class too large ({class_line_count}/{limits['max_class_lines']}). Split into smaller classes with single responsibilities.",
                    }
                )

            if rules["max_complexity"] and complexity > limits["max_complexity"]:
                issues.append(
                    {
                        "severity": "WARNING",
                        "message": f"Class too complex ({complexity}/{limits['max_complexity']}). Decompose into focused classes or extract complex methods.",
                    }
                )

            if rules["max_boolean_conditions"]:
                issues.extend(analyze_boolean_complexity(node, limits))
            if rules["max_if_else_chain"]:
                issues.extend(analyze_if_else_chain(node, limits))
            cls.append(
                {
                    "name": node.name,
                    "file": file_path,
                    "lines": class_line_count,
                    "issues": issues,
                }
            )

            if rules["empty_except"]:
                issues.extend(analyze_empty_except(node, limits))

    file_line_count = len(source_code.splitlines())
    file_issues = []

    if rules["max_file_lines"] and file_line_count > limits["max_file_lines"]:
        file_issues.append(
            {
                "severity": "WARNING",
                "message": f"File too large ({file_line_count}/{limits['max_file_lines']}). Split into modules or move unrelated code to separate files.",
            }
        )

    return (
        funcs,
        [{"name": file_path, "lines": file_line_count, "issues": file_issues}],
        cls,
    ) 
