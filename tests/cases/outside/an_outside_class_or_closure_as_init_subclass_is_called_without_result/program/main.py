
import contextlib
import threading
def g():
    yield
class A:
    __init_subclass__ = threading.Thread
class B(A):
    pass
class C:
    __init_subclass__ = contextlib.contextmanager(g)
class D(C):
    pass
class E:
    __init_subclass__ = A.__subclasses__
class F(E):
    pass
