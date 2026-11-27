
def target(): pass
def put(self, name, value):
    value()
class D:
    pass
name = "__setattr__"
setattr(D, name, put)
def use():
    D().anything = target
