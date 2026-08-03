# lambda_demo.py

# Small lambda (should NOT trigger)
square = lambda x: x * x


# Small lambda (should NOT trigger)
add = lambda a, b: a + b


# Large lambda (should trigger)
large = lambda x: (
    ((x + 1) * (x + 2))
    + ((x + 3) * (x + 4))
    + ((x + 5) * (x + 6))
    + ((x + 7) * (x + 8))
)


def demo():

    # Small lambda (should NOT trigger)
    double = lambda x: x * 2

    # Large lambda (should trigger)
    process = lambda x: (
        ((x + 1) * (x + 2))
        + ((x + 3) * (x + 4))
        + ((x + 5) * (x + 6))
        + ((x + 7) * (x + 8))
    )

    return process(10)