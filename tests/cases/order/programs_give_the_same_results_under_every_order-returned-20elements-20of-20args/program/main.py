
def f(): pass
def g(): pass
def h(): pass
class Base:
    def __new__(cls, *args):
        return args[0]
    def pick(self, *args):
        return args[1]
    def me(*args):
        return args[0]
class A(Base):
    def run(self): pass
class B(Base):
    def run(self): pass
def first(*args):
    return args[0]
def last(*args):
    return args[-1]
def use(items):
    first(f, g)()
    first(*items)()
    first(*[h], g)()
    A(B()).run()
    B(A()).me().run()
    Base.pick(None, f, g, h)()
    last(f)()
use([g, h])
last(h)
