
def f(): pass
def g(): pass
def h(): pass

import ext
def endless():
    while True:
        ext.step()
    else:
        f()
    g()
def broken():
    while 1:
        if ext.done():
            break
    else:
        f()
    g()
