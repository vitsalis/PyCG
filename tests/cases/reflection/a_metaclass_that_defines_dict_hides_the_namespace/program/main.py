
def wrong(): pass
def right(): pass
class M(type):
    __dict__ = {}
class C(metaclass=M):
    __slots__ = ()
    x = staticmethod(wrong)
class D:
    __dict__ = {}
    x = staticmethod(right)
def hidden():
    for value in vars(C).values():
        value()
    C.__dict__["x"]()
def plain():
    vars(D)["x"]()
hidden()
plain()
