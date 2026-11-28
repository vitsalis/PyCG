
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def apply(x): return x
def second(a, b): return b
def use():
    for x in map(apply, [f], *()):
        x()
    for y in map(second, [g], [h], *()):
        y()
    for z in map(second, [1], *[[k]]):
        z()
use()
