
import inspect
class A:
    def m(self): pass
class B:
    def n(self): pass
class J:
    k = B
class H:
    k = J
def make(base):
    class F(base):
        pass
    for name, value in inspect.getmembers(F()):
        value()
make(A)
for _, v in inspect.getmembers(H()):
    for _, w in inspect.getmembers(v()):
        make(w)
