
def f(): pass
def g(): pass
def h(): pass

import sys
handler = f
handler()
globals()
handler = g
