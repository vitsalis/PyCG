
def f(): pass
def g(): pass
def h(): pass

import ext
def use():
    handler = f
    try:
        while True:
            break
        handler = g
    finally:
        ext.cleanup()
    handler()
