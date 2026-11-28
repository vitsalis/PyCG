
class It:
    def __iter__(self): return self
    def __next__(self): return It()
    def ping(self): pass
