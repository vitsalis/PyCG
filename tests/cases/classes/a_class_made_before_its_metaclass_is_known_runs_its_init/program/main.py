
class Inner(type):
    def __init__(cls, name, bases, namespace): pass
def c0(): return c1
def c1(): return c2
def c2(): return c3
def c3(): return c4
def c4(): return c5
def c5(): return c6
def c6(): return Inner
class Late(metaclass=c0()()()()()()()): pass
class Outer(type):
    def __new__(mcs, name, bases, namespace): return Late
class Made(metaclass=Outer): pass
