
class Key:
    def __hash__(self): return 1
def add(s, items):
    s.update(items)
add(set(), [Key()])
add(set(), (Key(),))
