
import inspect
import sys
import helpers
class C:
    def on_a(self): pass
class Holder:
    s = setattr
def f(): pass
def run(obj, kind):
    getattr(obj, "on_" + kind)()
run(helpers, sys.argv[1])
for _, v in inspect.getmembers(Holder()):
    v(C(), "on_b", f)
