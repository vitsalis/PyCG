
import collections.abc
class View(collections.abc.Sequence):
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(self): return 2
def use(x):
    list(iter(x))
def copy(x):
    list(x)
use(View())
copy(View())
