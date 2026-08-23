import json
import re
from pathlib import Path

BASELINE_DIR = Path(".avouch")
BASELINE_FILE = BASELINE_DIR / "baseline.json"

_COUNT = re.compile(r"\(\d+/\d+\)")

_cache = {}


def _rule_label(message):
    first = message.split(".", 1)[0]
    first = _COUNT.sub("", first).strip()
    return first or message


def _fingerprint(file, name, rule, line):
    return (rule, file, name, line)


def load_baseline():
    path = BASELINE_FILE
    if not path.exists():
        return None
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        raise ValueError(f"invalid baseline file: {exc}")
    if not isinstance(data, dict) or data.get("version") != 1 or "findings" not in data:
        raise ValueError("invalid baseline file: expected version 1 with findings list")
    findings = data.get("findings")
    if not isinstance(findings, list):
        raise ValueError("invalid baseline file: expected version 1 with findings list")
    fps = set()
    for entry in findings:
        if not isinstance(entry, dict):
            raise ValueError("invalid baseline file: findings must be objects")
        fps.add(_fingerprint(entry.get("file"), entry.get("name"), entry.get("rule"), entry.get("line")))
    _cache[key] = fps
    return fps


def _finding_key(item):
    return (item["file"], item["line"] or 0, item["rule"], item["name"])


def collect_findings(function_reports, file_reports, class_reports):
    findings = []
    for report in [*class_reports, *function_reports, *file_reports]:
        file_name = report.get("file", report["name"])
        for issue in report["issues"]:
            rule = issue.get("rule") or _rule_label(issue["message"])
            findings.append({"rule": rule, "file": file_name, "name": report["name"], "line": report.get("line")})
    findings.sort(key=_finding_key)
    return findings


def write_baseline(function_reports, file_reports, class_reports):
    findings = collect_findings(function_reports, file_reports, class_reports)
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "findings": findings}
    BASELINE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(findings)


def _filter_one(reports, baseline_set, counter):
    out = []
    for report in reports:
        file_name = report.get("file", report["name"])
        kept = []
        for issue in report["issues"]:
            rule = issue.get("rule") or _rule_label(issue["message"])
            fp = _fingerprint(file_name, report["name"], rule, report.get("line"))
            if fp in baseline_set:
                counter[0] += 1
            else:
                kept.append(issue)
        out.append({**report, "issues": kept})
    return out


def filter_reports(function_reports, file_reports, class_reports, baseline_set):
    counter = [0]
    nf = _filter_one(function_reports, baseline_set, counter)
    nfi = _filter_one(file_reports, baseline_set, counter)
    nc = _filter_one(class_reports, baseline_set, counter)
    return nf, nfi, nc, counter[0]
