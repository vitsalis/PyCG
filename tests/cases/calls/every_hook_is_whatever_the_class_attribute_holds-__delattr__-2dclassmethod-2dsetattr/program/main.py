import functools
def target(): pass
def hook(*args):
    return target()
class Helper:
    def run(self, *args):
        return target()
class Caller:
    def __call__(self, *args):
        return target()
class C:
    pass
setattr(C, "__delattr__", classmethod(hook))
def use():
    del C().anything
