
import functools
def deco(f):
    @functools.wraps(f)
    def wrapper(*args):
        return f(*args)
    return wrapper
@deco
def g(): pass
@deco
def h(): pass
def use():
    g()
