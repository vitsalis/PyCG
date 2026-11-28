
class Backwards(type):
    def __reversed__(cls):
        return iter([])
class Sequence(type):
    def __len__(cls):
        return 1
    def __getitem__(cls, index):
        return index
class Deck(metaclass=Backwards): pass
class Row(metaclass=Sequence): pass
reversed(Deck)
list(reversed(Row))
