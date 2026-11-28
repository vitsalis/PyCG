import functools
def target(): pass
def hook(*args):
    return target()
class C:
    __setattr__ = functools.partial(hook, 1)
def use():
    C().anything = 1
