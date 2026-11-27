
def f(): pass
def g(): pass
def h(): pass

import ext
def both():
    if ext.flag:
        handler = f
    elif ext.other:
        handler = g
    else:
        handler = h
    handler()
def one_branch():
    handler = f
    if ext.flag:
        handler = g
    handler()
