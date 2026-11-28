def target(): pass
def hook(self, name):
    return target
class C:
    pass
name = f"__getattribute__"
setattr(C, name, hook)
def use():
    C().anything()
