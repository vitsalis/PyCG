
class Sized:
    def __iter__(self): return iter([])
    def __len__(self): return 0
    def __length_hint__(self): return 0
class Hinted:
    def __iter__(self): return iter([])
    def __length_hint__(self): return 0
def copy(items):
    list(items)
def extend(items):
    [].extend(items)
def as_tuple(items):
    tuple(items)
copy(Sized())
copy(Hinted())
extend(Sized())
as_tuple(Sized())
