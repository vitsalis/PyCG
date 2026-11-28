
import ext
def f(): pass
def g(): pass

from typing import Generic, TypeVar
T = TypeVar("T")
class Box(Generic[T]):
    def __init__(self):
        pass
    def get(self):
        pass
class Stub(ext.Generic):
    def get(self):
        pass
def use():
    Box[int]().get()
    Stub[int]().get()
