
import abc
import inspect
class A(abc.ABC):
    def f(self): pass
class B(metaclass=abc.ABCMeta):
    def g(self): pass
def run():
    for name, value in inspect.getmembers(A):
        value(A())
    for value in vars(B).values():
        value(B())
run()
