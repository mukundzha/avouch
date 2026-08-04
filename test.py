# all_rules_demo.py


def monster(
    a,
    b,
    c,
    d,
    e,
    f,
    g,
):
    x1 = 1
    x2 = 2
    x3 = 3
    x4 = 4
    x5 = 5
    x6 = 6
    x7 = 7
    x8 = 8
    x9 = 9
    x10 = 10
    x11 = 11
    x12 = 12
    x13 = 13
    x14 = 14
    x15 = 15
    x16 = 16
    x17 = 17

    try:
        print(a)
    except:
        pass

    if a == 1:
        return 1
    elif a == 2:
        return 2
    elif a == 3:
        return 3
    elif a == 4:
        return 4
    elif a == 5:
        return 5
    elif a == 6:
        return 6
    elif a == 7:
        return 7

    def helper():
        return 42

    huge_lambda = lambda x: (
        ((x + 1) * (x + 2))
        + ((x + 3) * (x + 4))
        + ((x + 5) * (x + 6))
        + ((x + 7) * (x + 8))
    )

    huge_list = [
        (i + j) * k
        for i in range(10)
        for j in range(10)
        for k in range(5)
        if i > 2
        if j > 3
        if k > 1
    ]

    if a > 0 and b > 0 and c > 0 and d > 0 and e > 0 and f > 0:
        print("complex")

    return helper()