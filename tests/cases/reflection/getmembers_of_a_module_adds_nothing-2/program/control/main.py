
import inspect, math
class C:
    def f(self): pass
def run(x):
    for name, value in inspect.getmembers(x):
        value(C())
run(math)
run(C)
