
import tokenize
import typing
class Token(tokenize._TokenInfo):
    def ping(self): pass

def protocols(
    a: typing.Iterable[int],
    b: typing.Iterator[int],
    c: typing.Collection[int],
    d: typing.Container[int],
    e: typing.Sized,
    f: typing.Hashable,
    g: typing.Reversible[int],
):
    for each in (a, b, c, d, e, f, g):
        each.ping()

def sequence(s: typing.Sequence[int]):
    s.ping()
