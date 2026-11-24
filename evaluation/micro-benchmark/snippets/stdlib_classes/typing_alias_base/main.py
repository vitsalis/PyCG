from typing import AbstractSet, Iterator

class Countdown(Iterator):
    def __next__(self):
        raise StopIteration

class Empty(AbstractSet):
    def __contains__(self, item):
        return False

    def __iter__(self):
        yield from ()

    def __len__(self):
        return 0

Countdown().__iter__()
Empty().isdisjoint(())
