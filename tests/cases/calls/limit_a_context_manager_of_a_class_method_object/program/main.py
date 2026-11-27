
from contextlib import contextmanager
class C:
    @contextmanager
    @classmethod
    def cm(cls):
        yield cls
def use():
    C.cm().__enter__()
