class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

class Holder:
    value = []
Base = Holder.value.__class__
class Left(Base):
    pass
class Right(list):
    def append(self, x):
        pass
class Both(Left, Right):
    pass
def run():
    Both().append(0)
