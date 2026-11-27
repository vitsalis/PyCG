import functools
def target(): pass
def hook(*args):
    return target
class Helper:
    def run(self, *args):
        return target
class Caller:
    def __call__(self, *args):
        return target
class C:
    __getattr__ = lambda *args: target
def use():
    C().missing()
