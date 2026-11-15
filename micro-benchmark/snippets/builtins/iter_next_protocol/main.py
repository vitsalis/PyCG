class Numbers:
    def __iter__(self):
        return self

    def __next__(self):
        return 1

iterator = iter(Numbers())
next(iterator)
