
import enum
import inspect
def hit(): pass
class D:
    def __get__(self, obj, owner):
        hit()
class E(enum.Enum):
    A = 1
    hidden = D()
class P:
    hidden = D()
def of_the_class():
    inspect.getmembers(E)
def of_a_member():
    inspect.getmembers(E(1))
def default_directory():
    inspect.getmembers(P())
of_the_class()
of_a_member()
default_directory()
