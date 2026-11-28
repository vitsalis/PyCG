def f(): pass
def g(): pass
def h(): pass

import sys
def a(): return f
def b(): return g
for each in (iter(a, None) if sys.argv else iter(b, None)):
    each()
