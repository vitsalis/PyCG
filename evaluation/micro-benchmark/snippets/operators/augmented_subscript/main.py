class Counter:
    def __getitem__(self, key):
        return 0

    def __setitem__(self, key, value):
        pass


counter = Counter()
counter["a"] += 1
