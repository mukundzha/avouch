def generate_report(function_reports, file_reports, class_reports):

    print("SCRUT REPORT")
    print("=" * 50)
    print("=" * 50)

    total_issues = 0

    print("\nFILE")
    print("-" * 50)

    for report in file_reports:
        print(f"Name   : {report['name']}")
        print(f"Lines  : {report['lines']}")

        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  [{issue['severity']}] {issue['message']}")
            total_issues += len(report["issues"])
            print("")
            # print("==============================")
        else:
            print("Issues: None")

    print("\nFUNCTIONS")
    print("-" * 50)

    for index, report in enumerate(function_reports, start=1):

        print(f"\nFunction {index}: {report['name']}")
        print(f"Lines         : {report['lines']}")
        print(f"Parameters    : {report['parameters']}")
        print(f"Nesting Depth : {report['nesting_depth']}")

        if report["issues"]:
            print("Issues:")
            for issue in report["issues"]:
                print(f"  [{issue['severity']}] {issue['message']}")
            total_issues += len(report["issues"])
        else:
            print("Issues: None")

    print("\nCLASSES")
    print("-" * 50)

    if class_reports:

        for report in class_reports:

            print(f"\nClass: {report['name']}")
            print(f"Lines: {report['lines']}")

            if report["issues"]:
                print("Issues:")
                for issue in report["issues"]:
                    print(f"  [{issue['severity']}] {issue['message']}")
                total_issues += len(report["issues"])
            else:
                print("Issues: None")

    else:
        print("No classes found.")

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Functions Reviewed : {len(function_reports)}")
    print(f"Classes Reviewed   : {len(class_reports)}")
    print(f"Files Reviewed     : {len(file_reports)}")
    print(f"Issues Found       : {total_issues}")
    print("=" * 50)

