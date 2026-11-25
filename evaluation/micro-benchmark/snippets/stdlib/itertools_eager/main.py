import functools
import itertools
import math
import operator


class Countdown:
    def __init__(self):
        self.left = 2

    def __iter__(self):
        return self

    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return self.left


class Numbers:
    def __iter__(self):
        return Countdown()


def make(numbers):
    return itertools.product(numbers, repeat=1)


def consume(product):
    return list(product)


def total(numbers):
    return functools.reduce(operator.add, numbers, 0)


def dot(numbers):
    return math.sumprod(numbers, numbers)


consume(make(Numbers()))
total(Numbers())
dot(Numbers())
