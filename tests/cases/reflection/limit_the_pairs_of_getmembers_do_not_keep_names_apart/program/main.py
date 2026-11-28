
import inspect
def chosen(): pass
def other(): pass
class C:
    x = staticmethod(chosen)
    y = staticmethod(other)
def members():
    dict(inspect.getmembers(C))["x"]()
def pairs():
    dict([("x", chosen), ("y", other)])["x"]()
members()
pairs()
