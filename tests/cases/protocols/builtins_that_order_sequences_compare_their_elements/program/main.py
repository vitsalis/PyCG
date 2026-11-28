
class Item:
    def __eq__(self, other): return False
    def __lt__(self, other): return False
    def __gt__(self, other): return False
def use(pairs):
    pairs.sort()
    sorted(pairs)
    min(pairs)
def largest(pairs):
    return max(pairs)
use([(1, Item()), (2, Item())])
largest([(1, Item()), (2, Item())])
