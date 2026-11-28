
import collections.abc
BASE = collections.abc.Iterator
def widen(
    a=collections.abc.Sized,
    b=collections.abc.Hashable,
    c=collections.abc.Container,
):
    global BASE
    BASE = a
    BASE = b
    BASE = c
class Late:
    def ping(self): pass
