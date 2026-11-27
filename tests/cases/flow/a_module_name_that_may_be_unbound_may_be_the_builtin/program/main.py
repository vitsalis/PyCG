
def f(): pass
def g(): pass
def h(): pass

import ext
if ext.legacy:
    len = f
len()
