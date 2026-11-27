
class A:
    def __init_subclass__(cls):
        super().__init_subclass__()
class B:
    def __init_subclass__(cls): pass
class FirstMeta(type):
    def __init__(cls, name, bases, namespace): pass
class SecondMeta(FirstMeta):
    def __init__(cls, name, bases, namespace): pass
class First(metaclass=FirstMeta): pass
class Second(metaclass=SecondMeta): pass
def make():
    type("C", (A, B), {})
def meta():
    type("D", (First, Second), {})
make()
meta()
