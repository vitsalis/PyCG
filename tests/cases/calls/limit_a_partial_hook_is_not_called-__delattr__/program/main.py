import functools
def target(): pass
def hook(*args):
    return target()
class C:
    __delattr__ = functools.partial(hook, 1)
def use():
    del C().anything
