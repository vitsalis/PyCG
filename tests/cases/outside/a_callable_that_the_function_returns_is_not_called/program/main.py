
import abc
import typing
@typing.overload
def f(x: int) -> int: ...
def f(x): pass
class C:
    @abc.abstractmethod
    def m(self): pass
