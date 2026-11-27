
from typing import Protocol
class Wrapped(Protocol):
    @property
    def __wrapped__(self): pass
class Wrapper(Wrapped):
    __slots__ = ("__wrapped__",)
    def __init__(self, f):
        self.__wrapped__ = f
    def run(self):
        return self.__wrapped__
