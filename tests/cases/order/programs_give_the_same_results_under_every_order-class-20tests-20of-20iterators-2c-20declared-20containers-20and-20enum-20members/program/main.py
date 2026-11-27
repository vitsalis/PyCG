
from enum import Enum
def target(): pass
class L(list):
    def __getitem__(self, index): return tuple(self)
    def __add__(self, other): return tuple(self)
class D(dict):
    def items(self): return [[k, self[k]] for k in self]
def run():
    it = iter([target])
    if not isinstance(it, list):
        next(it)()
def use(x: list, d: dict):
    x.append(target)
    for y in (x[:], x + [], x * 2):
        if not isinstance(y, list):
            y[0]()
    d[target] = 0
    for pair in d.items():
        if isinstance(pair, list):
            pair[0]()
class E(Enum):
    A = [target]
    def __iter__(self): return iter(self.value)
def members(x=E.A):
    if not isinstance(x, list):
        for callback in x:
            callback()
run()
use(L(), D())
