
import lib
class Registry(lib.Registry):
    pass
class Signal(lib.Signal):
    pass
class C:
    value = property(lib.get)
    def __call__(self): pass
class D:
    value = property(lib.a.b.c)
    def __call__(self): pass
class Task(lib.Future):
    pass
def handler(): pass
def listener(): pass
def use(flag):
    registry = Registry()
    registry["x"] = handler
    Signal() + listener
    obj = C() if flag else D()
    obj.value
    lib.register(Task())
    list(map(handler, [1]))
