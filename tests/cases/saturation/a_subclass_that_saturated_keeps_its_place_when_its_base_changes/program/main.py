
def h0(self): pass
def h1(self): pass
def h2(self): pass
def h3(self): pass
def h4(self): pass
HANDLERS = [h0, h1, h2, h3, h4]
def pick():
    for h in HANDLERS:
        return h
class Mixin:
    def run(self): pass
def c0(): return c1
def c1(): return c2
def c2(): return c3
def c3(): return c4
def c4(): return c5
def c5(): return c6
def c6(): return Mixin
class Late(c0()()()()()()()): pass
class Sub(Late, pick()): pass
def use():
    Late().run()
    Sub().run()
use()
