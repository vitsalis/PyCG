
import inspect
class A:
    def m(self): pass
class B(A): pass
class C(A): pass
class D(B, C): pass
def run():
    for name, value in inspect.getmembers(D()):
        value()
