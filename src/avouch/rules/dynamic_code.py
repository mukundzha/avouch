import ast

from avouch.utility.walk import walk


def analyze(function_node, limits):
    if any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"eval", "exec"}
        for node in walk(function_node)
    ):
        return [{
            "rule": "SCR020",
            "severity": "ERROR",
            "message": "Dynamic code execution with eval() or exec() can execute untrusted input. Avoid it or use a safe alternative.",
        }]
    return []
