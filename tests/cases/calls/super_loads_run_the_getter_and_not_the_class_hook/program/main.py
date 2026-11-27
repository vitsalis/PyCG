
class Base:
    pass
class Plain:
    def get(self): pass
    def change(self, value): pass
    def remove(self): pass
    item = property(get, change, remove)
class Replacing:
    def get(self): pass
    def change(self, value): pass
    def remove(self): pass
    item = property(get, change, remove)
    def __getattribute__(self, name):
        return None
    def __setattr__(self, name, value):
        self.__dict__[name] = value
    def __delattr__(self, name): pass
class Delegating(Base):
    def get(self): pass
    def change(self, value): pass
    def remove(self): pass
    item = property(get, change, remove)
    def __getattribute__(self, name):
        return object.__getattribute__(self, name)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
    def __delattr__(self, name):
        Base.__delattr__(self, name)
class Inheriting(Replacing):
    pass
class Restoring(Replacing):
    __getattribute__ = object.__getattribute__
    __setattr__ = object.__setattr__
    __delattr__ = object.__delattr__

class Child(Replacing):
    def via_super(self):
        return super().item
Child().via_super()
