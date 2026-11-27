def target(): pass
def hook(self, name):
    return target
class C:
    pass
setattr(C, "__getattr__", hook)
def use():
    C().missing()
