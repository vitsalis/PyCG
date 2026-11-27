
def first(self, name):
    return object.__getattribute__(self, name)
def third(self, name):
    return object.__getattribute__(self, name)
def later():
    return lambda: lambda: lambda: third
def pick(flag):
    return first if flag else later()()()()
class C:
    __getattribute__ = pick(True)
    @property
    def a(self):
        return 1
    @property
    def b(self):
        return 1
c = C()
c.a
def use(x):
    return x.b
def delay():
    return lambda: lambda: lambda: lambda: lambda: lambda: lambda: lambda: use
delay()()()()()()()()()(c)
