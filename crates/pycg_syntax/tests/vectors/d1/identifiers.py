import os . path as p
from . import sibling
from .. pkg . sub import (name as alias, other)
from os import *


def outer(ﬁrst, *args, key=1, **kwargs):
    count = 0

    def inner():
        nonlocal count
        global total
        count += 1

    return inner(key=count, **kwargs)


class Point[T, *Ts, **P]:
    __match_args__ = ("x", "y")


match outer:
    case Point(x=0, y=[*rest]) as matched:
        pass
    case {"k": v, **others}:
        pass
    case [first, *_]:
        pass
    case _:
        pass

try:
    pass
except ValueError as error:
    pass

try:
    pass
except* OSError:
    pass

value = os.path.join
spaced = t"{ x }{x=}{ x = !r}{x!r:>{width}}{ (x ) }{ x , }"
lines = t"""{x # note
}{ a +
 b # other
 , c}{x\
 }"""
formatted = f"{x!r:>{width}} {x=}"
