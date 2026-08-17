import ast

from scrut.utility.walk import walk

DECISION_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.Match,
    ast.IfExp,
    ast.Assert,
    ast.With,
    ast.AsyncWith,
    ast.BoolOp,
)
def calculate_complexity(function_node):
    complexity = 1

    for node in walk(function_node):

        if isinstance(node, DECISION_NODES):
            complexity += 1

        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1

    return complexity