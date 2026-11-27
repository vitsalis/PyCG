
import collections
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
def look(table, key):
    table.get(key)
    table.pop(key, None)
    table.setdefault(key, 1)
    key in table
    return table
ordered = collections.OrderedDict()
ordered[Key()] = 1
look(ordered, Key()).move_to_end(Key())
look({Key(): 2}, Key())
