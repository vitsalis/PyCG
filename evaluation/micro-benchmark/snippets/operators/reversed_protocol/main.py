class Deck:
    def __reversed__(self):
        return iter([])

    def __len__(self):
        return 0


class Row:
    def __len__(self):
        return 1

    def __getitem__(self, index):
        return index


reversed(Deck())
list(reversed(Row()))
