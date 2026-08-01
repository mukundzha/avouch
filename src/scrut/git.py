import subprocess
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
    return result.stdout.splitlines()


def get_reviewable_files(files):
    reviewable = []

    for file in files:
        path = Path(file)

        if path.suffix == ".py" and path.exists():
            reviewable.append(str(path))

    return reviewable