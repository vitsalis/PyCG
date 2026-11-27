
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True

class Value:
    def __eq__(self, other): return True
def dicts(a, b):
    return a == b
def sets(a, b):
    return a != b
dicts({Key(): Value()}, {Key(): Value()})
sets({Key()}, frozenset([Key()]))
