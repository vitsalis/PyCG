def target(): pass
def hook(self, name, value):
    value()
class C:
    pass
name = f"__setattr__"
setattr(C, name, hook)
def use():
    C().anything = target
