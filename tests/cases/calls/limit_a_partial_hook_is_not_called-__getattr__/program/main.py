import functools
def target(): pass
def hook(*args):
    return target
class C:
    __getattr__ = functools.partial(hook, 1)
def use():
    C().missing()
