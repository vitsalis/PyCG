
def wrong(): pass
def real(): pass
class Base:
    hook = staticmethod(wrong)
    def __init_subclass__(cls):
        cls.hook()
class Existing(Base):
    hook = staticmethod(real)
def make():
    type("Dynamic", (Base,), {"hook": staticmethod(real)})
make()
