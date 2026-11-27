
class Item:
    def touch(self): pass
class Needle:
    def __eq__(self, other):
        other.touch()
        return True

class Bag:
    def __contains__(self, item): return False
class Holder:
    items = Bag()
name = "items"
Needle() in getattr(Holder, name)
