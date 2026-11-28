
class Verdict:
    def __bool__(self): return True
class Item:
    def keep(self): return Verdict()
    def run(self): pass
def pick():
    return CHOSEN
def items():
    return ITEMS
def use():
    for item in filter(pick(), items()):
        item.run()
    filter(filter, [items()])
CHOSEN = Item.keep
ITEMS = [Item()]
use()
