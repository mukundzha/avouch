import ast
from avouch.utility.walk import walk


def analyze(function_node, limits):
    for node in walk(function_node):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr in {"run", "call", "check_call", "check_output", "Popen"}
            and any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
        ):
            return [{
                "rule": "SCR019",
                "severity": "ERROR",
                "message": "subprocess call uses shell=True. Avoid shell execution or pass a safely constructed argument list.",
            }]
    return []
