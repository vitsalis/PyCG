
import bisect
class Item:
    def ping(self): pass
class Needle:
    def ping(self): pass
def rank(item):
    item.ping()
def find(items):
    return bisect.bisect_left(items, 1, key=rank), bisect.bisect(items, 1, key=rank)
def place(items):
    bisect.insort(items, Needle(), key=rank)
def plain(items):
    bisect.bisect_right(items, 1)
find([Item()])
place([Item()])
plain([Item()])
