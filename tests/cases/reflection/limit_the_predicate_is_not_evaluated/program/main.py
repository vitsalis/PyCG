
import inspect
class A:
    def f(self): pass
def run():
    for name, member in inspect.getmembers(A, lambda value: False):
        member(A())
run()
