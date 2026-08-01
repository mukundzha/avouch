from scrut.config.loader import load_config
from scrut.config.default import DEFAULT_LIMITS
from scrut.analyzer import analyze_file
from scrut.report import generate_report
from scrut.git import is_gitrepo, get_changed_files, get_reviewable_files
       
def main():

    config = load_config()
    limits = config.get("limits", DEFAULT_LIMITS)

    if not is_gitrepo():
        print("Not inside a Git repository.")
        return

    changed_files = get_changed_files()
    reviewable_files = get_reviewable_files(changed_files)

    if not reviewable_files:
        print("No Python files to review.")
        return

    file_reports = []
    functions_reports = []
    class_reports = []

    for file_path in reviewable_files:
        functions, files, classes = analyze_file(file_path, limits)
        functions_reports.extend(functions)
        file_reports.extend(files)
        class_reports.extend(classes)

    generate_report(functions_reports, file_reports, class_reports)


if __name__ == "__main__":
    main()
