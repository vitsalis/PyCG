
import inspect
class A:
    def _f_one(self): pass
    def _f_two(self): pass
def run():
    for name, member in inspect.getmembers(A, inspect.isfunction):
        member(A())
run()
