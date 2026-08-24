import io
import ast
import tokenize
from pathlib import Path


def _line_offsets(source):
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _position_offset(source, offsets, position):
    row, column = position
    line = source.splitlines(keepends=True)[row - 1]
    character_column = len(line.encode("utf-8")[:column].decode("utf-8", errors="ignore"))
    return offsets[row - 1] + character_column


def fix_bare_except(file_path):
    """Replace bare except clauses with ``except Exception``.

    Returns the number of clauses changed. The tokenizer keeps comments,
    strings, and formatting outside the replacement untouched.
    """

    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    replacements = []

    significant = [
        token
        for token in tokens
        if token.type not in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE}
    ]

    for index, token in enumerate(significant[:-1]):
        following = significant[index + 1]
        if token.type == tokenize.NAME and token.string == "except":
            if following.type == tokenize.OP and following.string == ":":
                replacements.append(following.start)

    if not replacements:
        return 0

    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    for row, column in reversed(replacements):
        offset = offsets[row - 1] + column
        source = source[:offset] + " Exception" + source[offset:]

    path.write_text(source, encoding="utf-8")
    return len(replacements)


def fix_mutable_default_args(file_path):
    """Replace mutable defaults with ``None`` and initialize them in-body."""

    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    offsets = _line_offsets(source)
    edits = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.body:
            continue

        defaults = list(zip(node.args.args[-len(node.args.defaults) :], node.args.defaults))
        defaults.extend(
            (arg, default)
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
            if default is not None
        )
        mutable = [
            (arg.arg, default)
            for arg, default in defaults
            if isinstance(default, (ast.List, ast.Dict, ast.Set))
            or (
                isinstance(default, ast.Call)
                and (
                    isinstance(default.func, ast.Name)
                    and default.func.id in {"list", "dict", "set", "bytearray", "defaultdict", "OrderedDict"}
                    or isinstance(default.func, ast.Attribute)
                    and default.func.attr in {"list", "dict", "set", "bytearray", "defaultdict", "OrderedDict"}
                )
            )
        ]
        if not mutable:
            continue

        first_statement = node.body[0]
        has_docstring = (
            isinstance(first_statement, ast.Expr)
            and isinstance(first_statement.value, ast.Constant)
            and isinstance(first_statement.value.value, str)
        )
        if has_docstring and len(node.body) > 1:
            first_statement = node.body[1]
        if first_statement.lineno == node.lineno:
            continue

        source_lines = source.splitlines(keepends=True)
        statement_line = source_lines[first_statement.lineno - 1]
        indent = statement_line[: len(statement_line) - len(statement_line.lstrip())]
        initialization = "".join(
            f"{indent}if {name} is None:\n{indent}    {name} = "
            f"{ast.get_source_segment(source, default)}\n"
            for name, default in mutable
        )
        if has_docstring and len(node.body) == 1:
            insertion = offsets[first_statement.end_lineno]
        else:
            insertion = _position_offset(source, offsets, (first_statement.lineno, 0))
        edits.append((insertion, insertion, initialization))

        for _, default in mutable:
            start = _position_offset(source, offsets, (default.lineno, default.col_offset))
            end = _position_offset(source, offsets, (default.end_lineno, default.end_col_offset))
            edits.append((start, end, "None"))

    if not edits:
        return 0

    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    path.write_text(source, encoding="utf-8")
    return sum(1 for start, end, replacement in edits if replacement == "None")
