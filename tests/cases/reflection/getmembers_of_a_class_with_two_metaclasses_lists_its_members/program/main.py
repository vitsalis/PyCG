
import inspect
import sys
class Meta(type):
    pass
class A(metaclass=Meta if sys.argv else type):
    def m(self): pass
def run():
    for name, value in inspect.getmembers(A):
        value(A())
