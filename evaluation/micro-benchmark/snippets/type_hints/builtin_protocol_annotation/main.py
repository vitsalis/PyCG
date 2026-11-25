import collections.abc
import pickle
import typing


class Line(collections.abc.Sequence):
    def __init__(self):
        self.items = [1, 2]

    def __getitem__(self, index):
        return self.items[index]

    def __len__(self):
        return 2

    def __iter__(self):
        return iter(self.items)


class Names(list):
    def __iter__(self):
        yield "never"


def drain(numbers: typing.Iterable[int]) -> None:
    for number in numbers:
        pass


drain(pickle.loads(pickle.dumps(Line())))
