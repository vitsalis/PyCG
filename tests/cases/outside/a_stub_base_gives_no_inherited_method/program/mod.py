
import collections.abc
class Half:
    def __next__(self): raise StopIteration
class Full(collections.abc.Iterator):
    def __next__(self): raise StopIteration
def loop(half: Half, full: Full):
    for x in half:
        pass
    for y in full:
        pass
def lookup(half: Half):
    half.__iter__()
    half.__length_hint__()
