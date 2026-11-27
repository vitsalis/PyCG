
class Needle:
    def __eq__(self, other): return False
class Bag:
    def __contains__(self, item): return False
def bag():
    Needle() in Bag()
def full():
    Needle() in [1]
class Item:
    def __eq__(self, other): return True
def untracked():
    None in [Item()]
