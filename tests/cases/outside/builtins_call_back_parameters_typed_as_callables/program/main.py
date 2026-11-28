
import functools
import threading
def key(x): pass
def double(x): pass
def keep(x): pass
def add(a, b): pass
def work(): pass
def use():
    sorted([3, 1], key=key)
    list(map(double, [1, 2]))
    list(filter(keep, [1]))
    functools.reduce(add, [1, 2])
    threading.Thread(target=work)
