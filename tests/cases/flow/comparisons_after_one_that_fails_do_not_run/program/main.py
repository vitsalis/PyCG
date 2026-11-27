
def f(): pass
def g(): pass
def h(): pass

import ext
def known():
    handler = f
    2 < 1 < (handler := g)
    handler()
def unknown():
    handler = f
    ext.a < ext.b < (handler := g)
    handler()
