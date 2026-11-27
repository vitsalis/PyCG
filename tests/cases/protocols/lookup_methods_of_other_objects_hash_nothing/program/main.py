
class Key:
    def __hash__(self): return 1
class Table:
    def get(self, key): pass
[Key()].pop(0)
Table().get(Key())
