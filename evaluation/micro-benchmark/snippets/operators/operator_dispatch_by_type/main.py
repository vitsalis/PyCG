class Money:
    def __add__(self, other):
        return self


class Duration:
    def __add__(self, other):
        return self


def combine(a, b):
    return a + b


combine(Money(), Money())
combine(1, 2)
Duration()
