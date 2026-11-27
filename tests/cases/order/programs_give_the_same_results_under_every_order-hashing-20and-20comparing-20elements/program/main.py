
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
    def __lt__(self, other): return False
class Sized:
    def __iter__(self): return iter([])
    def __len__(self): return 0
def use(items, keys, table, pairs):
    {*items}
    set(items).union(keys)
    keys.discard(Key())
    dict.fromkeys(items)
    table.update(pairs)
    sorted(pairs)
    list(LATE)
    return pairs == [(1, Key())] and table != {Key(): 2}
items = []
keys = set()
table = {}
pairs = []
use(items, keys, table, pairs)
items.append(Key())
keys.add(Key())
pairs.append((1, Key()))
table[Key()] = 1
LATE = Sized()
