
class Item:
    def __str__(self): return "s"
    def __repr__(self): return "r"
def fmt():
    return LATE
def use(item):
    text = fmt()
    text % (item,)
    text %= {"k": item}
LATE = "%(k)s %r"
use(Item())
