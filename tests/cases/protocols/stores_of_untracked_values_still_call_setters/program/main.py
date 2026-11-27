
class C:
    def __setitem__(self, key, value): pass
    def change(self, value): pass
    def other(self, value): pass
    item = property(fset=change)
    flag = property(fset=other)
    noted = property(fset=other)
def use(c):
    c[0] = None
    c.item = None
    c.item, c.flag = 1.5, True
def make():
    return C()
def key():
    return 0
def annotate(c):
    c.noted: int
    make().noted: int
    c[key()]: int
use(C())
annotate(C())
