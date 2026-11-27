
def f(): pass
def g(): pass
def h(): pass

import ext
def broken():
    handler = f
    for item in ext.items:
        handler = g
        if ext.done:
            handler = h
            break
        handler = f
    handler()
def continued():
    for item in ext.items:
        handler = g
        if ext.skip:
            handler = h
            continue
        handler = f
    handler()
def otherwise():
    handler = f
    while ext.more():
        handler = g
        if ext.done:
            break
        handler = h
    else:
        handler()
