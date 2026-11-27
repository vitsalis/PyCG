
import typing
items = [1]
table = {"a": 1}
class Base:
    __init_subclass__ = items.copy
class Derived(Base):
    pass
