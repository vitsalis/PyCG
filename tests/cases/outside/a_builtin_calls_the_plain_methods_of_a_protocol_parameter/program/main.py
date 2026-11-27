
class Log:
    def write(self, text): pass
    def flush(self): pass
    def report(self):
        print("x", file=self)
class Table:
    def keys(self): return ["a"]
    def __getitem__(self, key): return 1
    def __iter__(self): return iter([])
Log().report()
frozendict(Table())
