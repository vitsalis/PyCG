
def f(): pass
class Table:
    def __getitem__(self, key):
        return f
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
def use(table):
    table["a"]()
    table[1:2]
    table["b"] = 1
    del table["c"]
use(Table())
