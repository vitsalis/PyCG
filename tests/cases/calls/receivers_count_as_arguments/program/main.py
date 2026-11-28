
class Base:
    def __init__(self, value): pass
    def method(self): pass
    @classmethod
    def make(cls): pass
    @staticmethod
    def util(): pass
class Empty:
    def __init__(self): pass
def build(kind):
    obj = kind()
    obj.method()
    kind.make()
    kind.util()
build(Base)
build(Empty)
