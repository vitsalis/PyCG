
import functools
def first(f):
    @functools.wraps(f)
    def inner_first(): return f()
    return inner_first
def second(f):
    @functools.wraps(f)
    def inner_second(): return f()
    return inner_second
@first
def a(): pass
@second
def b(): pass
a()
b()
