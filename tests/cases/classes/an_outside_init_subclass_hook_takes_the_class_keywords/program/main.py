
import itertools
class Base:
    __init_subclass__ = itertools.groupby
class Derived(Base, key=None): pass
