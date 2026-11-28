
import inspect
class Base:
    __init_subclass__ = inspect.getmembers
class Derived(Base):
    pass
