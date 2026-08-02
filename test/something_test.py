def empty_except():
    try:
        x = 10 / 0
    except:
        pass


def empty_except_specific():
    try:
        int("abc")
    except ValueError:
        pass


def valid_except():
    try:
        int("abc")
    except ValueError:
        print("Invalid number")


def valid_raise():
    try:
        int("abc")
    except ValueError:
        raise


def valid_return():
    try:
        int("abc")
    except ValueError:
        return