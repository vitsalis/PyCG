
def target(): pass
def put(self, name, value):
    value()
class C:
    __setattr__ = put
C().anything = target
