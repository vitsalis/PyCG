import itertools
class Seq:
    def __len__(self): return 1
    def __getitem__(self, index): return index
class Items:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
def double(x): return x
def keep(x): return True
def triple(x): return x
def make():
    return map(double, Items()), filter(keep, [1]), zip(Items()), enumerate(Items()), reversed(Seq())
def advance(lazy):
    for item in lazy:
        pass
def build():
    for lazy in make():
        advance(lazy)
def chained():
    return itertools.chain(map(triple, [1]))
def take():
    next(chained())
build()
take()
