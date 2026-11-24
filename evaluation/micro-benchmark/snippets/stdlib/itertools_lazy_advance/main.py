import itertools


class Item:
    def ping(self):
        pass


class Countdown:
    def __init__(self):
        self.left = 2

    def __iter__(self):
        return self

    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return Item()


class Source:
    def __iter__(self):
        return Countdown()


def make(source):
    return itertools.islice(source, 2)


def returned(source):
    return itertools.takewhile(bool, source)


def consume(lazy):
    for item in lazy:
        item.ping()


def step(lazy):
    return next(lazy)


consume(make(Source()))
returned(Source())
step(itertools.cycle(Source()))
