
class Base:
    def __new__(cls, *args):
        return args[0]
class A(Base): pass
class B(Base): pass
class X:
    def m(self): pass
class Y:
    def m(self): pass
def use():
    A(X()).m()
B(Y()).m()
