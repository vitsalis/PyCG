
class Item:
    def __repr__(self): return "item"
    def __str__(self): return "s"
formats = []
items = []
table = {}
for fmt in formats:
    fmt % items
    fmt % table
formats.append("%s")
formats.append("%(a)s")
items.append(Item())
table["a"] = Item()
items.append(items)
