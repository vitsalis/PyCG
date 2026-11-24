from collections.abc import Sequence

def func1():
    pass

def func2():
    pass

class Pair(Sequence):
    def __getitem__(self, index):
        return (func1, func2)[index]

    def __len__(self):
        return 2

match Pair():
    case [first, second]:
        second()
