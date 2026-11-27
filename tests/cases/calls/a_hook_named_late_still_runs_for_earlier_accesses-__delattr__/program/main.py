def target(): pass
def hook(self, name):
    target()
class C:
    pass
name = f"__delattr__"
setattr(C, name, hook)
def use():
    del C().anything
