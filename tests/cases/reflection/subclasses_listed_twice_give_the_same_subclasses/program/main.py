
class A:
    pass
class B(A):
    def m(self): pass
def first():
    A.__subclasses__()[0].m(None)
def second():
    A.__subclasses__()[0].m(None)
