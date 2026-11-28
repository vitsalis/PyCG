
import inspect
class Hidden:
    __dict__ = {}
    def __dir__(self):
        return []
class M(type, Hidden):
    pass
class N(Hidden, type):
    pass
class C(metaclass=M):
    def f(self): pass
class K(metaclass=N):
    def g(self): pass
def namespace():
    vars(C)["f"](C())
def members():
    dict(inspect.getmembers(C))["f"](C())
def hidden_namespace():
    vars(K)["g"](K())
def hidden_members():
    dict(inspect.getmembers(K))["g"](K())
namespace()
members()
hidden_namespace()
hidden_members()
