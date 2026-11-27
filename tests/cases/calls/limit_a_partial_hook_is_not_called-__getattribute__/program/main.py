import functools
def target(): pass
def hook(*args):
    return target
class C:
    __getattribute__ = functools.partial(hook, 1)
def use():
    C().anything()
