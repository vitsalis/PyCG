
import functools
import heapq
class Item:
    def ping(self): pass
def compare(a, b):
    a.ping()
    return 0
KEY = functools.cmp_to_key(compare)
def order(items):
    return sorted(items, key=KEY), min(items, key=KEY), heapq.nsmallest(1, items, KEY)
def wrap(item):
    return KEY(item)
order([Item()])
wrap(Item())
