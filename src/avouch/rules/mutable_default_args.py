import ast


MUTABLE_LITERALS = (
    ast.List,
    ast.Dict,
    ast.Set,
)

MUTABLE_CONSTRUCTORS = {
    "list",
    "dict",
    "set",
    "bytearray",
    "defaultdict",
    "OrderedDict",
}


def is_mutable_default(default):

    if isinstance(default, MUTABLE_LITERALS):
        return True

    if isinstance(default, ast.Call):
        func = default.func

        if isinstance(func, ast.Name):
            return func.id in MUTABLE_CONSTRUCTORS

        if isinstance(func, ast.Attribute):
            return func.attr in MUTABLE_CONSTRUCTORS

    return False


def analyze(function_node, limits):

    issues = []

    for default in function_node.args.defaults + function_node.args.kw_defaults:

        if default is None or not is_mutable_default(default):
            continue

        issues.append(
            {
                "rule": "SCR017",
                "severity": "WARNING",
                "message": (
                    "Mutable default argument detected. Defaults are evaluated "
                    "once at definition time; use None and construct the "
                    "object inside the function instead."
                ),
            }
        )

    return issues
