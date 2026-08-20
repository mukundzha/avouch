import ast

from avouch.utility.walk import walk
from avouch.rules.complexity import calculate_complexity
from avouch.rules.max_nesting import get_depth
from avouch.rules.boolean_complexity import count_boolean_conditions

LIMIT_KEYS = [
    "max_parameters",
    "max_nesting",
    "max_function_lines",
    "max_class_lines",
    "max_file_lines",
    "max_complexity",
    "max_boolean_conditions",
    "max_if_chain",
    "max_local_variables",
    "max_return_statements",
    "max_lambda_nodes",
    "max_large_comprehensions",
]


def _longest_if_chain(function_node):

    longest = 0

    for node in walk(function_node):

        if not isinstance(node, ast.If):
            continue

        chain_length = 1
        current = node

        while len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            chain_length += 1
            current = current.orelse[0]

        longest = max(longest, chain_length)

    return longest


def _count_local_variables(function_node):

    variables = set()

    for node in walk(function_node):

        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:

            if isinstance(target, ast.Name):
                variables.add(target.id)

    return len(variables)


def _measure_function(node, maxima, rules):

    if rules.get("max_parameters"):
        maxima["max_parameters"] = max(maxima["max_parameters"], len(node.args.args))

    if rules.get("max_nesting"):
        maxima["max_nesting"] = max(maxima["max_nesting"], get_depth(node))

    if rules.get("max_function_lines"):
        maxima["max_function_lines"] = max(
            maxima["max_function_lines"], node.end_lineno - node.lineno + 1
        )

    if rules.get("max_complexity"):
        maxima["max_complexity"] = max(maxima["max_complexity"], calculate_complexity(node))

    if rules.get("max_boolean_conditions"):
        maxima["max_boolean_conditions"] = max(
            maxima["max_boolean_conditions"],
            max(
                (
                    count_boolean_conditions(child)
                    for child in walk(node)
                    if isinstance(child, ast.BoolOp)
                ),
                default=0,
            ),
        )

    if rules.get("max_if_else_chain"):
        maxima["max_if_chain"] = max(maxima["max_if_chain"], _longest_if_chain(node))

    if rules.get("max_lambda_nodes"):
        maxima["max_lambda_nodes"] = max(
            maxima["max_lambda_nodes"],
            max(
                (
                    len(list(walk(child.body)))
                    for child in walk(node)
                    if isinstance(child, ast.Lambda)
                ),
                default=0,
            ),
        )

    if rules.get("max_local_variables"):
        maxima["max_local_variables"] = max(
            maxima["max_local_variables"], _count_local_variables(node)
        )

    if rules.get("max_return_statements"):
        maxima["max_return_statements"] = max(
            maxima["max_return_statements"],
            sum(1 for child in walk(node) if isinstance(child, ast.Return)),
        )

    if rules.get("max_large_comprehensions"):
        maxima["max_large_comprehensions"] = max(
            maxima["max_large_comprehensions"],
            max(
                (
                    len(list(walk(child)))
                    for child in walk(node)
                    if isinstance(
                        child,
                        (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
                    )
                ),
                default=0,
            ),
        )


def _measure_class(node, maxima, rules):

    if rules.get("max_class_lines"):
        maxima["max_class_lines"] = max(
            maxima["max_class_lines"], node.end_lineno - node.lineno + 1
        )

    if rules.get("max_complexity"):
        maxima["max_complexity"] = max(maxima["max_complexity"], calculate_complexity(node))

    if rules.get("max_boolean_conditions"):
        maxima["max_boolean_conditions"] = max(
            maxima["max_boolean_conditions"],
            max(
                (
                    count_boolean_conditions(child)
                    for child in walk(node)
                    if isinstance(child, ast.BoolOp)
                ),
                default=0,
            ),
        )

    if rules.get("max_if_else_chain"):
        maxima["max_if_chain"] = max(maxima["max_if_chain"], _longest_if_chain(node))


def measure_maxima(file_paths, rules):

    maxima = dict.fromkeys(LIMIT_KEYS, 0)

    for file_path in file_paths:

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                source = file.read()
        except (OSError, UnicodeDecodeError):
            continue

        try:
            parsed = ast.parse(source)
        except SyntaxError:
            continue

        if rules.get("max_file_lines"):
            maxima["max_file_lines"] = max(maxima["max_file_lines"], len(source.splitlines()))

        for node in ast.walk(parsed):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _measure_function(node, maxima, rules)
            elif isinstance(node, ast.ClassDef):
                _measure_class(node, maxima, rules)

    return maxima