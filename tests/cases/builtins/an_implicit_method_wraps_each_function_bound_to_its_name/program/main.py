
import sys
def first(cls): pass
def second(cls): pass
class Base:
    __init_subclass__ = first if sys.argv else second
class Derived(Base):
    pass
