
def target(): pass
def put(self, name, value):
    value()
class D:
    pass
setattr(D, "__setattr__", put)
def use():
    D().anything = target
