import subprocess
from scrut.utility.is_generated import is_generated
from scrut.utility.is_ignored import is_ignored
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
        ["git", "diff", "HEAD", "--", file_path], capture_output=True, text=True
    )

    return result.stdout


def get_all_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def get_reviewable_files(files, ignore_paths=()):

    reviewable = []

    for file in files:
        path = Path(file)

        if (
            path.suffix == ".py"
            and not is_generated(path)
            and not is_ignored(file, ignore_paths)
            and path.exists()
        ):
            reviewable.append(str(path))

    return reviewable