import collections.abc
import pickle


class Countdown(collections.abc.Sequence):
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return index

    def __len__(self):
        return 2


class Ticker:
    def __getitem__(self, index):
        raise IndexError

    def __len__(self):
        return 0


def first(numbers: collections.abc.Sequence) -> None:
    numbers[0]
    len(numbers)


first(pickle.loads(pickle.dumps(Countdown())))
