import io
import re
import tokenize

_RE_AV_IGNORE_FILE = re.compile(r"#\s*avouch\s*:\s*ignore-file\s*(?:\[([^\]]+)\])?", re.IGNORECASE)
_RE_AV_IGNORE = re.compile(r"#\s*avouch\s*:\s*ignore\s*(?:\[([^\]]+)\])?", re.IGNORECASE)
_RE_NOQA = re.compile(r"#\s*noqa\s*(?::\s*([A-Za-z0-9,\s]+))?", re.IGNORECASE)
_RE_CODE = re.compile(r"^(SCR\d+|CPLX)$", re.IGNORECASE)


def _parse_codes(raw):
    if raw is None:
        return None
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    codes = set()
    for p in parts:
        if _RE_CODE.match(p):
            codes.add(p)
    return codes if codes else set()


def parse_suppressions(source):
    file_suppress = None
    line_suppress = {}
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return file_suppress, line_suppress
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        text = tok.string
        line = tok.start[0]
        m = _RE_AV_IGNORE_FILE.search(text)
        if m:
            raw = m.group(1)
            codes = _parse_codes(raw) if raw is not None else None
            file_suppress = codes
            continue
        m = _RE_AV_IGNORE.search(text)
        if m:
            raw = m.group(1)
            codes = _parse_codes(raw) if raw is not None else None
            line_suppress[line] = codes
            continue
        m = _RE_NOQA.search(text)
        if m:
            raw = m.group(1)
            if raw is None and ":" not in text.lower().split("noqa", 1)[-1]:
                line_suppress[line] = None
            elif raw is not None:
                codes = _parse_codes(raw)
                if codes is not None:
                    line_suppress[line] = codes
                elif raw.strip() == "":
                    line_suppress[line] = None
            else:
                line_suppress[line] = None
    return file_suppress, line_suppress


def is_suppressed(rule_id, line, file_suppress, line_suppress):
    if file_suppress is not None:
        if file_suppress is None or not file_suppress or rule_id in file_suppress:
            return True
    if line is None:
        return False
    codes = line_suppress.get(line)
    if codes is None and line in line_suppress:
        return True
    if codes is not None and rule_id in codes:
        return True
    return False
