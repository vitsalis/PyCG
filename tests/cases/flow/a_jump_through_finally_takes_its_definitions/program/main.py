
def f(): pass
def g(): pass
def h(): pass

import ext
def use():
    handler = f
    for item in ext.items:
        try:
            if ext.done:
                break
        finally:
            handler = g
        handler = h
    handler()
