
def f(): pass
def g(): pass
def h(): pass

import contextlib, ext
def use():
    handler = f
    with contextlib.suppress(KeyError):
        handler = ext.table["key"]
        handler = g
    handler()
