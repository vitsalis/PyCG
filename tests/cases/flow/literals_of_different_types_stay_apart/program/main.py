
def f(): pass
def g(): pass
def h(): pass

import ext
def identity():
    value = True if ext.flag else 1
    if value is not True:
        f()
def matched():
    value = 1 if ext.flag else True
    match value:
        case True:
            g()
def equal():
    if 1 == True:
        h()
