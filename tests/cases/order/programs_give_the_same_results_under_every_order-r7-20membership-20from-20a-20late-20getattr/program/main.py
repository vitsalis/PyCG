
class Item:
    def touch(self): pass
class Needle:
    def __eq__(self, other):
        other.touch()
        return True
class Holder:
    items = [Item()]
name = "items"
Needle() in getattr(Holder, name)
