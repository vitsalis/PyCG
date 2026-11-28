
class Hook:
    def __init__(self, **options): pass
class Base:
    __init_subclass__ = Hook
class Derived(Base): pass
