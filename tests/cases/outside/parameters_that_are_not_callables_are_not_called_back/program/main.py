
import copy
import inspect
import typing
class C:
    def __call__(self): pass
def f(): pass
def use():
    isinstance(f, C)
    callable(C())
    inspect.isclass(f)
    copy.copy(f)
    sorted([f, C()])
    "".join([f])
    print(f)
