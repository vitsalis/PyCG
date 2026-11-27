
def target(): pass
def other(): pass
class Getter:
    def get(self, obj):
        return obj.handler
class Caller:
    def __call__(self, obj):
        return obj.spare
class C:
    def __init__(self):
        self.handler = target
        self.spare = other
    value = property(Getter().get)
    called = property(Caller())
def use():
    C().value()
    C().called()
