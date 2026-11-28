
from contextlib import contextmanager
def action(): pass
@contextmanager
def managed():
    yield action
def make():
    return managed()
def use():
    cm = make()
    with cm as value:
        value()
