
class Item:
    def __repr__(self): return "r"
class Key:
    def __repr__(self): return "k"
def late():
    return LATE
def show(xs):
    repr(xs)
    f"{xs}"
    "%s" % (xs,)
box = [late()]
box.append(box)
show(box)
show({Key(): (late(),)})
LATE = Item()
