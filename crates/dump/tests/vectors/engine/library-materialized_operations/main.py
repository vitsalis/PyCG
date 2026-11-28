import functools
import heapq
import itertools


class Item:
    def run(self):
        pass

    def score(self):
        return 1


def make():
    return [Item()]


def combine(left, right):
    return left


for pair in itertools.combinations(make(), 2):
    pair[0].run()
for item in heapq.nlargest(1, make(), key=Item.score):
    item.run()
functools.reduce(combine, make())
total = sum(itertools.islice(make(), 1))
joined = ",".join(itertools.islice(["a"], 1))
