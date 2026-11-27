
def f(): pass
def g(): pass
def h(): pass

import ext
handler = f
class C:
    handler()
    if ext.flag:
        handler = g
    handler()
    handler = h
