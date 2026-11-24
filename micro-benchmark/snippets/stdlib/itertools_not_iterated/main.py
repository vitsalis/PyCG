import collections
import heapq
import itertools


class Countdown:
    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration


class Names(list):
    def __iter__(self):
        return Countdown()


def repeated(value):
    return next(itertools.repeat(value))


def chained(mapping):
    return collections.ChainMap(mapping)


def heap(names):
    heapq.heapify(names)


repeated(Countdown())
chained({})
heap(Names([2, 1]))
