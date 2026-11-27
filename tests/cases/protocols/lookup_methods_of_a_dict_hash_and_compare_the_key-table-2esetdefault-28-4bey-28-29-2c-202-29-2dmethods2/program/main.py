
import collections
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
def look(table):
    table.setdefault(Key(), 2)
look({Key(): 1})
