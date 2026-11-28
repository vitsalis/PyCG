
def f(): pass
def g(): pass
def h(): pass

import ext
def handled():
    handler = f
    try:
        handler = g
        ext.risky()
        handler = h
    except ValueError:
        handler()
def after():
    handler = f
    try:
        handler = g
        ext.risky()
        handler = h
    except ValueError:
        return
    handler()
