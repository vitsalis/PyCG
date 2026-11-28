
import types
class C:
    def m(self): pass
def f(): pass
types.MethodType(f, C())()
