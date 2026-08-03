def no_nested():
    x = 10
    return x


def one_nested():

    def helper():
        return 42

    return helper()


def multiple_nested():

    def first():
        return 1

    def second():
        return 2

    return first() + second()


def deeply_nested():

    def level1():

        def level2():
            return 100

        return level2()

    return level1()