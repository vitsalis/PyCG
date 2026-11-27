
import sys
class C:
    def on_a(self): pass
def run(obj, kind):
    getattr(obj, "on_" + kind)()
run(C(), sys.argv[1])
run(C(), sys.argv[1])
