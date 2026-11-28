
class Verdict:
    def __bool__(self): return True
class Item:
    def keep(self): return Verdict()
    def run(self): pass
class Other:
    def run(self): pass
def first(pair):
    return pair[0].keep()
def unused(): pass
def use():
    for item in filter(first, [(Item(), unused)]):
        item[0].run()
    for kept in filter(Item.keep, [Item()]):
        kept.run()
use()
