
class A: pass
def c1(): return c2
def c2(): return c3
def c3(): return c4
def c4(): return c5
def c5(): return c6
def c6(): return c7
def c7(): return A
def use():
    for sub in A.__subclasses__():
        sub().m()
use()
class B(c1()()()()()()()):
    def m(self): pass
