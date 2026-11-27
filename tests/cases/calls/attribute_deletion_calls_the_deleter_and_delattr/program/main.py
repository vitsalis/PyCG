
class C:
    def remove(self): pass
    item = property(fdel=remove)
class D:
    def __delattr__(self, name): pass
def use(c, d):
    del c.item
    del d.anything
def builtin(c):
    delattr(c, "item")
use(C(), D())
builtin(C())
