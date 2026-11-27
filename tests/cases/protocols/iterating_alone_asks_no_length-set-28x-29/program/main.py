import collections

import ext
class Sized:
    def __iter__(self): return iter([])
    def __len__(self): return 0
class Hinted:
    def __iter__(self): return iter([])
    def __length_hint__(self): return 0
def f(*args): pass

def use(x):
    set(x)
use(Sized())
use(Hinted())
