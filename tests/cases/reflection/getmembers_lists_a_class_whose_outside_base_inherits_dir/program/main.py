
import inspect
class C(int):
    def f(self): pass
def use():
    for name, value in inspect.getmembers(C()):
        value()
use()
