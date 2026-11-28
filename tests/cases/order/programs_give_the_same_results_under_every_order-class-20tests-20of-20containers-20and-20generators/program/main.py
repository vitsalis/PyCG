
import collections
from collections.abc import Sequence
class A:
    def f(self): pass
class B:
    def f(self): pass
class Items(list):
    def f(self): pass
def made():
    yield A()
async def run():
    return B()
def kinds(): return (tuple, collections.OrderedDict)
def parse(arg, *args, declared: list[A] = None, **kwargs):
    classes = kinds()
    for x in (arg, args, kwargs, declared):
        if isinstance(x, classes):
            for v in x:
                v.f()
        elif not isinstance(x, (list, dict)):
            x.f()
        if isinstance(x, Sequence):
            x[0].f()
        first, *rest = x
        if isinstance(rest, tuple):
            rest[0].f()
parse([A()][0:], B())
parse((B(),) + (A(),), k=A())
parse(made())
parse(run())
parse(Items())
parse(dict([(A(), B())]).copy())
parse(collections.OrderedDict(a=A()))
parse(x for x in [B()])
for pair in zip([A()], [B()]):
    parse(pair)
