
class Base:
    def method(self): pass
class Field:
    def __set_name__(self, owner, name): pass
class Child(Base):
    locals()
    field = Field()
    def method(self): pass
    def __init_subclass__(cls): pass
    if False:
        def other(self): pass
class Grandchild(Child):
    pass
Grandchild().method()
