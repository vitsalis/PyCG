
import collections.abc
class Store(collections.abc.MutableMapping):
    def __getitem__(self, key): pass
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __iter__(self): pass
    def __len__(self): pass
def use():
    Store().popitem()
    Store().no_such_method()
