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
    

def get_changed_files():
    result = subprocess.run(
        ["git" , "diff" , "--name-only"],
        capture_output=True,
        text=True
    )

    print("\n" + "Changed Files:" + "\n"+ result.stdout)
    return result.stdout.splitlines()


is_gitrepo()
get_changed_files()