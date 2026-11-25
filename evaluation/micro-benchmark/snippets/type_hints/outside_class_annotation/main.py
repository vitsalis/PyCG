import collections.abc
import pickle


class Countdown(collections.abc.Iterator):
    def __init__(self):
        self.left = 2

    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return self.left


class Ticker:
    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration


def drain(numbers: collections.abc.Iterator) -> None:
    for number in numbers:
        pass


drain(pickle.loads(pickle.dumps(Countdown())))
