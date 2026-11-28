import collections

class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
def use():
    dict([(Key(), 1), (Key(), 2)])
use()
