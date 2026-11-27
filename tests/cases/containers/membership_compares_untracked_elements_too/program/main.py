
class Item:
    def __eq__(self, other): return False
class Needle:
    def __eq__(self, other): return False
def displays():
    Item() in [None]
    Item() in (False, 1.5)
def stored():
    xs = []
    xs.append(None)
    Item() in xs
def copied():
    Item() in list([None])
def converted():
    Item() in list({None})
def yielding():
    yield None
def generated():
    Item() in list(yielding())
def keys():
    d = {}
    d[None] = 1
    Item() in d
def unpacked(*rest):
    return Item() in rest
unpacked(None)
