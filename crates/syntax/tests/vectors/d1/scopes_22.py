
import sys
def reads():
    x = 1
    return locals()
def described(obj):
    x = 1
    return vars(obj)
def shadowed():
    locals = dict
    x = 1
    return locals()
def runs():
    x = 1
    exec("y = 2")
