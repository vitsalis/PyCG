
def f(): pass
def g(): pass
def h(): pass

import ext
def joined():
    flag = True
    if ext.other:
        flag = False
    (f if flag else g)()
def mutated():
    pending = []
    pending.append(h)
    handler = pending and f
    handler()
def looped():
    done = False
    while ext.more():
        (f if done else g)()
        done = True
def wrapped():
    @ext.register
    def decorated(): pass
    (decorated or f)()
