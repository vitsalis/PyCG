import inspect
from inspect import iscoroutine
class A:
    pass
class B(A):
    pass
def f(x, y, t):
    if isinstance(x, (A, B)) and not callable(y):
        r = x
    elif issubclass(t, A):
        r = t
    if not (isinstance(x, A) or inspect.iscoroutine(x)):
        r = x
    if iscoroutine(y):
        r = y
    while isinstance(x, B):
        x = x
    assert callable(x)
    return isinstance(x, A, B), isinstance(f(x), A), r
