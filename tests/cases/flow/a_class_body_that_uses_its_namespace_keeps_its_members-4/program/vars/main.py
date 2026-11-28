
def f(): pass
def g(): pass
def h(): pass

class Base:
    def method(self):
        f()
    def other(self):
        f()
class Field:
    def __set_name__(self, owner, name):
        pass
class Plugin(Base):
    vars()
    field = Field()
    def method(self):
        g()
    def __init_subclass__(cls):
        cls()
    def __init__(self):
        pass
    def __call__(self):
        h()
    if False:
        def other(self):
            pass
class Concrete(Plugin):
    pass
def use():
    Plugin().method()
    Plugin().__init_subclass__()
    Plugin().other()
