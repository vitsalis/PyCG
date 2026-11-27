
class Seq:
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(self): return 2
class Hinted:
    def __getitem__(self, index):
        raise IndexError
    def __length_hint__(self): return 0
def f(*args): pass

def use(x):
    *rest, = x
use(Seq())
use(Hinted())
