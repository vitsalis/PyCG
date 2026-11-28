
class Item:
    def __eq__(self, other): return False
    def __lt__(self, other): return False
    def __le__(self, other): return False
def equal(a, b):
    return a == b
def less(a, b):
    return a < b
def nested(a, b):
    return a <= b
def other(a):
    return a == 1
equal([Item()], [Item()])
less((1, Item()), (1, Item()))
nested(((Item(),),), ((Item(),),))
other((Item(),))
