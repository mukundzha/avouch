import subprocess
import re
from avouch.utility.is_generated import is_generated
from avouch.utility.is_ignored import is_ignored
from pathlib import Path

def is_gitrepo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
    )
    return result.returncode == 0


def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "HEAD", "--name-only"], capture_output=True, text=True
    )
    changed = result.stdout.splitlines()

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    changed.extend(untracked.stdout.splitlines())

    return changed


def get_file_diff(file_path):
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", file_path],
        capture_output=True,
        text=True,
    )

    if tracked.returncode != 0:
        return None

    result = subprocess.run(
        ["git", "diff", "HEAD", "--", file_path],
        capture_output=True,
        text=True,
        errors="replace",
    )

    return result.stdout


def get_staged_files():

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
    )

    return result.stdout.splitlines()


def get_changed_line_ranges(file_paths, staged=False):
    """Return added-line ranges for each tracked file, including untracked files."""

    ranges = {}
    command = ["git", "diff"]
    if staged:
        command.append("--cached")
    command.extend(["--unified=0", "--no-ext-diff", "--"])

    for file_path in file_paths:
        try:
            result = subprocess.run(
                [*command, file_path], capture_output=True, text=True, errors="replace"
            )
        except StopIteration:
            result = None
        file_ranges = []
        for line in (result.stdout if result is not None else "").splitlines():
            match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                if count:
                    file_ranges.append((start, start + count - 1))
        if file_ranges:
            ranges[file_path] = file_ranges
        else:
            # Empty/unparseable diffs are treated as whole-file changes. This
            # also lets the analyzer report read and decode errors itself.
            ranges[file_path] = [(1, 10**9)]
    return ranges


def get_all_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


DISK_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "testenv",
    "__pycache__",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".eggs",
    ".egg-info",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "site-packages",
    "dist",
    "build",
}


def get_all_files_on_disk():
    """List every .py file under the current directory as relative paths,
    skipping well-known cache and environment directories (mirrors the
    .gitignore-based exclusion Git applies with get_all_files())."""

    files = []

    for path in sorted(Path(".").rglob("*.py")):

        if any(part in DISK_SKIP_DIRS for part in path.parts):
            continue

        files.append(str(path))

    return files


def get_reviewable_files(files, ignore_paths=()):

    reviewable = []

    for file in files:
        path = Path(file)

        if (
            path.suffix == ".py"
            and not is_generated(path)
            and not is_ignored(file, ignore_paths)
            and not any(part in DISK_SKIP_DIRS for part in path.parts)
            and path.exists()
        ):
            reviewable.append(str(path))

    return reviewable