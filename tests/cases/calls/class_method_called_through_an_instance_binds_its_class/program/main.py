
class Base:
    @classmethod
    def make(cls):
        return cls()
class Child(Base):
    def __init__(self): pass
def via_instance(obj):
    return obj.make()
via_instance(Child())
