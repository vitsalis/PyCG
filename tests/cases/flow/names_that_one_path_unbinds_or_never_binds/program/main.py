
def f(): pass
def g(): pass
def h(): pass

import ext
def deleted():
    handler = f
    if ext.flag:
        del handler
    handler()
def raised():
    handler = f
    try:
        handler = g
        raise ValueError()
    except ValueError:
        handler()
for item in ext.items:
    len = f
len()
