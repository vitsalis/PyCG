
def f(self): pass
class P(property):
    def __init__(self, getter):
        super().__init__(fget=getter)
class C:
    x = P(f)
def use(c: C):
    c.x
