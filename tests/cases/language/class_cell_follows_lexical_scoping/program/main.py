
class A:
    def g(self): pass
__class__ = A
def outer():
    __class__ = A
    class C:
        def g(self): pass
        def m(self):
            __class__.g(self)
    return C
class D:
    def g(self): pass
    def uses_global(self):
        global __class__
        __class__.g(self)
    def binds(self):
        __class__ = A
        __class__.g(self)
