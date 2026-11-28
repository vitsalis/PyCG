import functools
import itertools
import threading
import typing
import lib
async def coroutine(): pass
coroutine()
class Base:
    def __init__(self, first=None): pass
    def m(self): pass
class C(Base):
    def __getattr__(self, name): return name
    @property
    def p(self): return self
    def __iter__(self):
        yield 1
    def __call__(self, *args): pass
    def go(self):
        super().m()
class D:
    f = classmethod(C())
def gen():
    yield 1
@functools.wraps(gen)
def wrapped(): pass
@functools.lru_cache(maxsize=2)
def memo(): pass
c = C()
Base(*c)
c.p
c.missing
c.go()
D.f()
for x in c: pass
xs = [1, 2]
xs.append(3)
len(xs).bit_length()
sorted(c, key=gen)
open("f", opener=gen)
open("f", "rb", 0)
ys = list(xs)
xs.extend(ys)
lib.run(c)
staticmethod(gen)()
name = "p"
getattr(c, name)
getattr(c, ("P" + name).lower())
def typed(kind: type[Base]): pass
if not isinstance(c, (Base, D)):
    c.go()
def listed(items: typing.Sequence[int]): pass
super(Base, c).m()
class E:
    def idle(self): pass
E()
vars(C)
list(itertools.islice(c, 1))
threading.Thread(target=gen).start()
