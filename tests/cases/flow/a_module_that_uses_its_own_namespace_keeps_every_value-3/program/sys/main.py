
def f(): pass
def g(): pass
def h(): pass

import sys
handler = f
handler()
sys.modules[__name__]
handler = g
