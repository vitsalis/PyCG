class Sequence:
    def __getitem__(self, index):
        if index < 2:
            return index
        raise IndexError(index)


for item in Sequence():
    pass
