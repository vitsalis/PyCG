
from typing import Protocol
def work(): pass
class Wrapped(Protocol):
    @property
    def __wrapped__(self): pass
    def __getattr__(self, name): return work
def base():
    return Wrapped
class Wrapper(base()):
    __slots__ = ("__wrapped__", "__store")
    def __init__(self, f):
        self.__wrapped__ = f
        self.__store = f
    def run(self):
        self.__wrapped__()
        self.__store()
        self.missing()
Wrapper(work).run()
