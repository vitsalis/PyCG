import os, os.path as osp
from . import sibling
from .pkg import item as other
from json import loads, dumps as d
from star import *
x: int
y: int = 1
del y
G = 0
def f(a, /, b=lambda: 0, *args, c=lambda q: q, **kw):
    global G
    G = 1
    total = 0
    def inner():
        nonlocal total
        total += 1
        return total
    try:
        pass
    except ValueError as error:
        pass
    return inner
class C:
    __private = 1
    def method(self):
        return __class__, self.__private
    class Nested:
        def __deep(self):
            pass
type Alias = list[int]
match value:
    case {"k": captured, **rest}:
        pass
    case [first, *others] | (first, *others):
        pass
    case Point(x=px) as whole:
        pass
