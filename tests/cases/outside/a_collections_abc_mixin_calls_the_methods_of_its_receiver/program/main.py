from collections.abc import Mapping, MutableMapping, MutableSet, Sequence
class Table(MutableMapping):
    def __init__(self):
        self.data = {}
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value
    def __delitem__(self, key):
        del self.data[key]
    def __iter__(self):
        return iter(self.data)
    def __len__(self):
        return len(self.data)
class Fixed(Mapping):
    def __getitem__(self, key):
        return key
    def __iter__(self):
        return iter(())
    def __len__(self):
        return 0
    def get(self, key, default=None):
        return default
class Bag(MutableSet):
    def __init__(self):
        self.items = set()
    def __contains__(self, item):
        return item in self.items
    def __iter__(self):
        return iter(self.items)
    def __len__(self):
        return len(self.items)
    def add(self, item):
        self.items.add(item)
    def discard(self, item):
        self.items.discard(item)
class Plain(dict):
    def __getitem__(self, key):
        return key
    def __setitem__(self, key, value):
        pass
class Row(Sequence):
    def __getitem__(self, index):
        return index
    def __len__(self):
        return 1
def mappings():
    table = Table()
    table.get("a")
    table.setdefault("a", 1)
    table.popitem()
    Fixed().get("a")
    Plain().setdefault("a", 1)
def sets():
    bag = Bag()
    bag.add(1)
    bag.clear()
def sequences():
    Row().index(0)
