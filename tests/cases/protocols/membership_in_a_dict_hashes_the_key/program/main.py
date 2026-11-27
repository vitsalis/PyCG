
class Key:
    def __hash__(self): return 1
def member(key, table, items):
    return key in table, key in items
member(Key(), {}, [])
