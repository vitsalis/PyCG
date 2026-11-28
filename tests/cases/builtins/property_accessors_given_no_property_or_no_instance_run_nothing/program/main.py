
def f(self): pass
def g(self): pass
def run():
    property.getter(classmethod(f), g)
    p = property(f)
    p.__get__(None)
    p.__get__(None, None)
    property.__get__(p)
