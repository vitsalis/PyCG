class Peek:
    def __init__(self):
        self.left = 2

    def __iter__(self):
        return self

    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return self.left


class Bag:
    def __init__(self):
        self.items = [1]

    def __contains__(self, item):
        return item in self.items

    def __iter__(self):
        yield 1


def drain(numbers):
    for number in numbers:
        pass


def has(items):
    return 1 in items
