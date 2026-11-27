class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

class Pairs(dict):
    def items(self):
        return [[k, self[k]] for k in self]
class Items(list):
    def __getitem__(self, index):
        return tuple(self)
def sliced(x: list):
    x.append(A())
    y = x[:]
    if not isinstance(y, list):
        y[0].inside()
def added(x: list):
    x.append(A())
    y = x + []
    if not isinstance(y, list):
        y[0].after()
def repeated(x: list):
    x.append(A())
    y = x * 2
    if not isinstance(y, list):
        y[0].other()
def pairs(d: dict):
    d[A()] = 0
    for pair in d.items():
        if isinstance(pair, list):
            pair[0].more()
sliced(Items())
added(Items())
repeated(Items())
pairs(Pairs())
