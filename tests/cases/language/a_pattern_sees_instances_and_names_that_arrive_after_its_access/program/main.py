
import inspect
import sys
class C:
    def on_a(self): pass
class Holder:
    k = C
    s = setattr
def f(): pass
def g(self): pass
def run(obj, kind):
    getattr(obj, "on_" + kind)()
c = C()
run(c, sys.argv[1])
for _, v in inspect.getmembers(Holder()):
    run(v(), sys.argv[1])
    v.on_a = g
    v(c, "on_b", f)
