
import lib
class Item:
    def touch(self): pass
class Needle:
    def __eq__(self, other):
        other.touch()
        return True
class Bag:
    def __contains__(self, item): return False
class Holder:
    items = [Item()]
    bag = Bag()
class Marker:
    def __init__(self):
        self.payload = [Item()]
def compare(self, other):
    Holder.late = self.payload
    return False
Marker.__eq__ = compare
def first(values):
    return Marker() in values
lib.run(first)
name = "items"
other = "bag"
Needle() in getattr(Holder, name)
Needle() in getattr(Holder, other)
Needle() in Holder.late
Needle() in []
Needle() in b"abc"
