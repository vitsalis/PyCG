
import inspect
import lib
class C:
    def g(self): pass
def by_dir():
    for name in dir(C):
        getattr(C, name)(C())
def of_a_module():
    for name, value in inspect.getmembers(lib):
        value()
    vars(lib)["f"]()
    lib.__dict__["f"]()
def without_an_argument():
    h = lib.f
    vars()["h"]()
def control():
    vars(C)["g"](C())
by_dir()
of_a_module()
without_an_argument()
control()
