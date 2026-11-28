
import ext
class C:
    def a(self): pass
    def b(self): pass
    selector = "b"
def late():
    return getattr(C, "selector")
def run(obj, option: str = "a"):
    getattr(obj, option)()
    getattr(obj, late() if ext.flag else ext.name)()
run(C(), late())
