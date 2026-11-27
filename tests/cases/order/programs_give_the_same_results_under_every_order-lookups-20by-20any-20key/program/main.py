
def f(): pass
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
table = {}
table.get(1)
table[f] if f in table else None
keys = [1]
table.pop(keys[0], None)
table[Key()] = 0
keys.append(Key())
