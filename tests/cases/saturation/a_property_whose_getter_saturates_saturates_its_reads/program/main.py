
def h0(self): pass
def h1(self): pass
def h2(self): pass
def h3(self): pass
def h4(self): pass
HANDLERS = [h0, h1, h2, h3, h4]
def pick():
    for h in HANDLERS:
        return h
class C:
    p = property(pick())
def use():
    C().p.run()
use()
