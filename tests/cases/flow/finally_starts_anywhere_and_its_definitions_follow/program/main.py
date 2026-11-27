
def f(): pass
def g(): pass
def h(): pass

import ext
def inside():
    handler = f
    try:
        handler = g
        ext.run()
        handler = h
    finally:
        handler()
def after():
    handler = f
    try:
        ext.run()
    finally:
        handler = g
    handler()
def normal():
    handler = f
    try:
        handler = g
        ext.run()
        handler = h
    finally:
        ext.cleanup()
    handler()
