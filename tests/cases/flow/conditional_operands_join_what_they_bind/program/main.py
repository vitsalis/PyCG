
def f(): pass
def g(): pass
def h(): pass

import ext
def either():
    handler = f
    ext.flag or (handler := g)
    handler()
def chosen():
    handler = f
    (handler := g) if ext.flag else None
    handler()
