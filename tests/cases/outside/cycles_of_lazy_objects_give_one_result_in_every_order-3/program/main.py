
import heapq
import itertools
import parts
class Holder:
    def __init__(self, it):
        self.it = it
    def step(self):
        self.it = itertools.islice(self.it, 1)
        for x in self.it:
            x.ping()
def base():
    return SOURCE
def loop(xs):
    acc = base()
    for x in xs:
        acc = itertools.chain(acc, x)
    return list(acc)
def tees(x):
    a, b = itertools.tee(x)
    c, d = itertools.tee(a)
    return list(c), list(d), list(b), list(b)
def merged(x):
    return list(heapq.merge(x, itertools.chain.from_iterable([x])))
Holder(parts.It()).step()
loop([parts.It(), parts.It()])
tees(parts.It())
merged(parts.It())
SOURCE = parts.It()
