
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
def h0(): pass
def h1(): pass
def h2(): pass
def h3(): pass
def h4(): pass
def run(handler):
    handler()
for handler in [h0, h1, h2, h3, h4]:
    run(handler)
