
def f(): pass
def g(): pass
def h(): pass

import sys
def namespace():
    handler = f
    handler()
    locals()
    handler = g
def evaluated():
    handler = f
    handler()
    eval("handler")
    handler = g
def described():
    handler = f
    handler()
    vars()
    handler = g
def shadowed():
    vars = ext.vars
    handler = f
    handler()
    vars()
    handler = g
def other_object(value):
    handler = f
    handler()
    vars(value)
    handler = g
import ext
