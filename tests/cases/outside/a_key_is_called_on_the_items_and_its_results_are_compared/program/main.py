
class Key:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
class Item:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
    def rank(self): return Key()
def key(item):
    return item.rank()
def by_sorted(items):
    sorted(items, key=key)
def by_min(a, b):
    min(a, b, key=key)
def by_max(items):
    max(items, key=key, default=None)
def by_sort(items):
    items.sort(key=key)
by_sorted([Item(), Item()])
by_min(Item(), Item())
by_max([Item(), Item()])
by_sort([Item(), Item()])
