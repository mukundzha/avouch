import subprocess

def is_gitrepo():
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        return True
    else:
        return False

is_gitrepo()