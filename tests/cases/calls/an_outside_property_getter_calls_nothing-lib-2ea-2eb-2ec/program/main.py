
import lib
class C:
    value = property(lib.a.b.c)
    def __call__(self): pass
class D:
    value = property(lib.a.b.c)
    def __call__(self): pass
def use(flag):
    obj = C() if flag else D()
    obj.value
