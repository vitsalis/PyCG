class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

from collections.abc import Iterable, Sequence
from typing import Generic, Protocol, TypeVar, runtime_checkable
T = TypeVar("T")
class Loops:
    def __iter__(self): return iter(())
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Registered:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
Sequence.register(Registered)
@runtime_checkable
class Runs(Protocol):
    def inside(self): ...
class Box(Generic[T]):
    def inside(self): pass
def structural(x=Loops()):
    if isinstance(x, Iterable):
        x.inside()
def registered(x=Registered()):
    if isinstance(x, Sequence):
        x.inside()
    else:
        x.after()
def protocol(x=Other()):
    if isinstance(x, Runs):
        x.other()
def generic(x=Other()):
    if isinstance(x, Box):
        x.more()
