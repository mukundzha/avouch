# comprehension_demo.py

# Small list comprehension (should NOT trigger)
numbers = [x * 2 for x in range(10)]


# Small set comprehension (should NOT trigger)
values = {x for x in range(5)}


# Large list comprehension (should trigger)
large_list = [
    (x + y) * z
    for x in range(10)
    for y in range(10)
    for z in range(5)
    if x % 2 == 0
    if y > 3
    if z != 2
]


# Large dictionary comprehension (should trigger)
large_dict = {
    (x, y): x * y
    for x in range(10)
    for y in range(10)
    if x > 3
    if y > 4
    if x != y
}


def demo():

    # Small generator (should NOT trigger)
    gen = (x * 2 for x in range(10))

    # Large generator (should trigger)
    big_gen = (
        (x + y) * z
        for x in range(10)
        for y in range(10)
        for z in range(5)
        if x > 1
        if y > 2
        if z > 3
    )

    return list(big_gen)