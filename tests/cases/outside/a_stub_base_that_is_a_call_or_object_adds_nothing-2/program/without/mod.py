
import collections.abc
import sys
class Peek:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def ping(self): pass
class Measured:
    def __len__(self): return 0
    def ping(self): pass
class Versioned:
    def ping(self): pass
class Outer:
    class Inner:
        def ping(self): pass
class Plain:
    def ping(self): pass
class Called:
    def ping(self): pass
