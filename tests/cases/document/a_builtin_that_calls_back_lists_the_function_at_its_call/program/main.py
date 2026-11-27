def f(x): pass
def key(x): pass
class Sized:
    def __len__(self): return 0
list(map(f, [1]))
sorted([2], key=key)
len(Sized())
