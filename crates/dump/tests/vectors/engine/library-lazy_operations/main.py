import itertools


class Item:
    def run(self):
        pass


def make():
    return [Item()]


for item in itertools.chain.from_iterable([make()]):
    item.run()
for item in itertools.islice(make(), 1):
    item.run()
for item in itertools.compress(make(), [True]):
    item.run()
for item in itertools.accumulate(make(), initial=Item()):
    item.run()
left, right = itertools.tee(make())
for item in left:
    item.run()
for key, group in itertools.groupby(make()):
    key.run()
    for item in group:
        item.run()
for first, second in itertools.pairwise(make()):
    second.run()
