
import inspect
class Hidden:
    def __dir__(self):
        return []
class Plain:
    pass
def pick(flag):
    return Hidden if flag else Plain
class C(pick(input())):
    def f(self): pass
def members():
    for name, value in inspect.getmembers(C()):
        value()
members()
