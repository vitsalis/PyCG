def target(): pass
def hook(self, name):
    return target
class C:
    pass
C.__getattr__ = hook
def use():
    C().missing()
