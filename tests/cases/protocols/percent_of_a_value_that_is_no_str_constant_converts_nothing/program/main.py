
class Item:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Formatter:
    def __mod__(self, other): return "m"
def use(item, unknown):
    Formatter() % item
    7 % item
    b"%s" % (item,)
    unknown % (item,)
    ("%" + unknown) % (item,)
use(Item(), None)
