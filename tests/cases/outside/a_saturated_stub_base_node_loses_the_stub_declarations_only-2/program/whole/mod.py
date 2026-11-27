
import collections.abc
class Wide:
    def ping(self): pass
class Own(collections.abc.Iterator):
    def __next__(self): raise StopIteration
    def ping(self): pass
Wide().ping()
