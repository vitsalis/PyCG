
def f(): pass
def g(): pass
def h(): pass

import ext
def use():
    line = f
    while line := ext.read():
        line()
    line()
