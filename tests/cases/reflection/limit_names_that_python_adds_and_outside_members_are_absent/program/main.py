
import inspect
class C:
    def f(self): pass
for name in vars(C):
    own = name
for name, value in inspect.getmembers(C):
    member = name
