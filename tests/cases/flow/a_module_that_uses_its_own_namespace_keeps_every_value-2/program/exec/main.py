
def f(): pass
def g(): pass
def h(): pass

import sys
handler = f
handler()
exec("pass")
handler = g
