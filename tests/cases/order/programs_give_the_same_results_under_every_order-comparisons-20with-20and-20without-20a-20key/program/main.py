
class Key:
    def __gt__(self, other): return False
class Item:
    def __lt__(self, other): return False
    def rank(self): return Key()
def key(item): return item.rank()
def order(items, *rest, **options):
    items.sort(key=key)
    sorted(*rest, **options)
    return max(items, *rest, key=Item)
order([Item()], [Item()], key=key)
order([Item()], [Item()])
class Meta(type):
    def __lt__(cls, other): return False
    def __reversed__(cls): return iter([])
class Ranked(metaclass=Meta): pass
sorted([Ranked, Item], key=lambda c: c)
reversed(Ranked)
