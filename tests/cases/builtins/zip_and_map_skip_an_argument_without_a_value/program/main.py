
def f(*args): pass
class Caller:
    __call__ = map
class Y:
    pass
Y.__new__ = Caller()
def run(xs):
    zip(None, xs)
    map(f, None, xs)
    Y(f, None)
