
def f(*args): pass
class Caller:
    __call__ = map
class Y:
    pass
Y.__new__ = Caller()
def run(xs):
    zip(None, xs)
    list(map(f, None, xs))
    list(Y(f, None))
