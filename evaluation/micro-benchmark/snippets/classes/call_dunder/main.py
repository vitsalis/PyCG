class Adder:
    def __call__(self, x):
        return x + 1


class Doubler:
    def __call__(self, x):
        return x * 2


def apply(op, value):
    return op(value)


adder = Adder()
doubler = Doubler()
apply(adder, 1)
