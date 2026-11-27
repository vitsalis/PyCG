import heapq
import itertools


class Item:
    def run(self):
        pass

    def score(self):
        return 1


def make():
    return [Item()]


for item in itertools.chain(make(), make()):
    item.run()
for first, second in itertools.zip_longest(make(), make()):
    first.run()
for first, second in itertools.product(make(), make()):
    second.run()
for first, second in itertools.product(make(), repeat=2):
    first.run()
for item in heapq.merge(make(), make(), key=Item.score):
    item.run()
