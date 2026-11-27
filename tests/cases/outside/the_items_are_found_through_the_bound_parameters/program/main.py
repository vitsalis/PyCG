
class Item:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
class Fallback:
    def __lt__(self, other): return False
    def __gt__(self, other): return False
def key(item): return item
def unpacked(items):
    sorted(*[items])
def arguments(a, b, c):
    max(*[a, b], c)
def with_default(items):
    max(items, default=Fallback())
def sort(items):
    items.sort()
def options(items, **kwargs):
    sorted(items, **kwargs)
unpacked([Item(), Item()])
arguments(Item(), Item(), Item())
with_default([Item(), Item()])
sort([Item(), Item()])
options([Item()])
options([Item()], key=key)
