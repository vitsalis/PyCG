
import collections.abc
import typing
class Names(list):
    def ping(self): pass
class Stream(Names, collections.abc.Iterator):
    def __next__(self): pass
    def ping(self): pass
def use(xs: typing.Iterable[str]):
    xs.ping()
