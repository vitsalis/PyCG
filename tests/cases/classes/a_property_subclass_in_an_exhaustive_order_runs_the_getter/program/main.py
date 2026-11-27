
import sys
class X1: pass
class Y1: pass
class X2: pass
class Y2: pass
class X3: pass
class Y3: pass
class Plain:
    def describe(self): pass
class P(
    property if sys.argv else Plain,
    X1 if sys.argv else Y1,
    X2 if sys.argv else Y2,
    X3 if sys.argv else Y3,
):
    pass
def read(self): pass
class Item:
    value = P(read)
def use():
    Item().value.describe()
use()
