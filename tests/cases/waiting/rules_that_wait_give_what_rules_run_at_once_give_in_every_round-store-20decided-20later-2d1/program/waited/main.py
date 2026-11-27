
def f(): pass
def g(): pass
class Field:
    def __get__(self, obj, owner=None): return f
    def __set__(self, obj, value): obj.written()
class Lazy:
    def __get__(self, obj, owner=None): return g
def later(): return lambda: lambda: Field()
class C:
    lazy = Lazy()
    def written(self): pass
class D(C):
    pass
def store(x):
    x.field = g
    x.lazy = f
    x.plain = f
    x.slow = g
    return x.field, x.lazy, x.plain, x.slow
for x in (C(), C(), D()):
    for value in store(x):
        value()
C.field = Field()
D.slow = later()()()
