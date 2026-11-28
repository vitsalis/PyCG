
import collections.abc
class OnlyItems:
    def __getitem__(self, index):
        return index
class OnlyLength:
    def __len__(self):
        return 1
class ItemsMeta(type):
    def __getitem__(cls, index):
        return index
class Keyed(metaclass=ItemsMeta): pass
class View(collections.abc.Sequence):
    def __getitem__(self, index):
        return index
    def __len__(self):
        return 1
list(reversed(OnlyItems()))
list(reversed(OnlyLength()))
list(reversed(Keyed))
list(reversed(View()))
