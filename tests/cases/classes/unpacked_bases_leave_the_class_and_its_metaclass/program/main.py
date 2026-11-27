
class A:
    def f(self): pass
class Meta(type):
    def __init__(cls, name, bases, namespace): pass
bases = (A,)
class C(*bases):
    def g(self): pass
class D(*bases, metaclass=Meta): pass
C().g()
