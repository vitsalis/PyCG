
import collections.abc
import typing
import mod
def base():
    return BASE
class Late(base()):
    def __next__(self): pass
    def ping(self): pass
class Later(Late):
    def ping(self): pass
def use(items: typing.Iterable[str], sized: typing.Sized):
    items.ping()
    sized.ping()
BASE = collections.abc.Iterator
