
from functools import partial
def first(): pass
def second(): pass
def invoke(cb): cb()
base = partial(invoke)
for p in (partial(base, first), partial(base, second)):
    p()
class Handler:
    def __init__(self, cb):
        cb()
for p in (partial(Handler, first), partial(Handler, second)):
    p()
def key(value):
    return value
list(map(partial(sorted, key=key), [[1]]))
def f(a, b): a()
partial(f, first)(second)
def old(): pass
def new(): pass
def call(*, cb): cb()
partial(call, cb=old)(cb=new)
def target(): pass
partial(target).func()
