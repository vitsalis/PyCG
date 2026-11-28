
import collections.abc
class Base(collections.abc.Iterator):
    def __next__(self): raise StopIteration
    def ping(self): pass
class Declared:
    def ping(self): pass
class Also:
    def ping(self): pass
class Stated(collections.abc.Iterator):
    def __next__(self): raise StopIteration
    def ping(self): pass
def check(base):
    base.ping()
