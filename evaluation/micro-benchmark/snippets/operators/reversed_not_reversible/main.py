class OnlyItems:
    def __getitem__(self, index):
        return index


class OnlyLength:
    def __len__(self):
        return 1


class Row:
    def __len__(self):
        return 1

    def __getitem__(self, index):
        return index


def backwards(sequence):
    try:
        return list(reversed(sequence))
    except TypeError:
        return []


backwards(OnlyItems())
backwards(OnlyLength())
backwards(Row())
