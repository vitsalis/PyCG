
import ext
def g(): pass
def star(a, cb=g):
    cb()
def double_star(a, cb=g):
    cb()
star(*ext.args)
double_star(1, **ext.kwargs)
