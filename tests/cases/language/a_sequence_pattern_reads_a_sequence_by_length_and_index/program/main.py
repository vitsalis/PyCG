
import ext
def f(): pass
def g(): pass
def h(): pass

from collections.abc import Sequence
class Pair(Sequence):
    def __getitem__(self, index):
        return (f, g)[index]
    def __len__(self):
        return 2
def use(value):
    match value:
        case [first, second]:
            second()
use(Pair())
