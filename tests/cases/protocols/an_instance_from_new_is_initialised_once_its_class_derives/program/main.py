
import sys
class X: pass
def c0(): return c1
def c1(): return c2
def c2(): return c3
def c3(): return c4
def c4(): return c5
def c5(): return c6
def c6(): return A
class A:
    def __new__(cls): return object.__new__(B)
    def __init__(self): pass
class B(X if sys.argv else c0()()()()()()()):
    def __init__(self): pass
A()
