class Seq:
    def __len__(self): return 1
    def __getitem__(self, index): return index
class Items:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
def double(x): return x
def keep(x): return True
def use():
    map(double, Items())
    filter(keep, Items())
    zip(Items())
    enumerate(Items())
    reversed(Seq())
use()
