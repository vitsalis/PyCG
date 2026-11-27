
def produce(): return 1
class Seq:
    def __getitem__(self, index): pass
def gen():
    yield 1
def make():
    return iter(produce, 0), iter(Seq()), gen()
def use(pair):
    first, second, third = pair
    first.__next__()
    second.__next__()
    third.__next__()
use(make())
