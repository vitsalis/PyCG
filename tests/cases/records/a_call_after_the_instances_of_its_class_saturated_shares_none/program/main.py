
class C:
    def __new__(cls):
        return object.__new__(cls)
    def __init__(self):
        pass
class D(C):
    pass
class E(C):
    pass
class K1:
    def next(self): return K2()
class K2:
    def next(self): return K3()
class K3:
    def next(self): return C
class L:
    def d(self): return D
    def e(self): return E
def early():
    C()
def middle():
    L().d()()
    L().e()()
def late():
    K1().next().next().next()()
early()
middle()
late()
