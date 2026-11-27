
class Item:
    def __eq__(self, other): return False
class Seq:
    def __getitem__(self, index): return None
class Items:
    def __iter__(self): return iter([None])
def generate():
    yield 1
    yield None
def unpacked(*rest):
    return rest
def nothing():
    return None
def keywords(**named):
    return named
def use():
    xs = next(iter({None: None}.items()))
    Item() in xs
