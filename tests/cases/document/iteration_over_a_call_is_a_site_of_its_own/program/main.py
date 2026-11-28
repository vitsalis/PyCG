class Items:
    def __iter__(self): return iter([])
def make(): return Items()
for x in make():
    pass
