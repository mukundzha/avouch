import io
import tokenize
from pathlib import Path


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
