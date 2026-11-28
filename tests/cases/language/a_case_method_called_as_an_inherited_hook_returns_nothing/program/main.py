
class Base:
    __init_subclass__ = "name".upper
class Derived(Base):
    pass
