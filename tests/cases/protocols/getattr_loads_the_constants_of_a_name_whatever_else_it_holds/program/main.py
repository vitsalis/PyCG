
import ext
class C:
    def a(self): pass
    def b(self): pass
    def c(self): pass
    def d(self): pass
    def e(self): pass
def annotated(obj, option: str = "a"):
    getattr(obj, option)()
def mixed(obj, flag):
    name = "b" if flag else ext.choose()
    setattr(obj, name, None)
    getattr(obj, name)()
def unknown(obj, option: str):
    getattr(obj, option)()
def many(obj, flag):
    for name in ("a", "b", "c", "d", "e", ext.choose()):
        getattr(obj, name)()
annotated(C())
mixed(C(), True)
unknown(C(), ext.option)
many(C(), True)
