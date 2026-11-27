
def f(): pass
def g(): pass
def h(): pass

import ext
def use():
    handler = f
    for outer in ext.items:
        for inner in ext.items:
            pass
        else:
            handler = g
            break
        handler = h
    handler()
