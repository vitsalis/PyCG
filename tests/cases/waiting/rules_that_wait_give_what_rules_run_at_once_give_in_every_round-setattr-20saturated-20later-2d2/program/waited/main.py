
def first(self, name, value):
    object.__setattr__(self, name, value)
def third(self, name, value):
    object.__setattr__(self, name, value)
def later():
    return lambda: lambda: lambda: third
def pick(flag):
    return first if flag else later()()()()
class C:
    __setattr__ = pick(True)
    @property
    def a(self):
        return 1
    @a.setter
    def a(self, value):
        pass
    @property
    def b(self):
        return 1
    @b.setter
    def b(self, value):
        pass
c = C()
c.a = 1
def use(x):
    x.b = 2
def delay():
    return lambda: lambda: lambda: lambda: lambda: lambda: lambda: lambda: use
delay()()()()()()()()()(c)
