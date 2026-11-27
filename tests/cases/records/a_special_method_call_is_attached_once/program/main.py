
class Sized:
    def __len__(self): return 1
    def __iter__(self): return iter(())
def measure(x):
    len(x)
    for item in x: pass
    return len(x)
measure(Sized()); measure(Sized())
