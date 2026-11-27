
def f(): pass
def g(): pass
def h(): pass

import ext
def use():
    handler = f
    if ext.flag:
        handler = g
        return
    elif ext.other:
        handler = g
        raise ValueError()
    handler()
