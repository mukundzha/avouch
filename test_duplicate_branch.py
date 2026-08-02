def example(user):
    if user.is_admin:
        send_email()

    elif user.is_staff:
        send_email()

    elif user.is_guest:
        log_access()