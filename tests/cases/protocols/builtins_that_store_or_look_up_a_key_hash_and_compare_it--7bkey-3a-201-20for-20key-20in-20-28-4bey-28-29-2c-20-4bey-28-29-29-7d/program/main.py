import collections

class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
def use():
    {key: 1 for key in (Key(), Key())}
use()
