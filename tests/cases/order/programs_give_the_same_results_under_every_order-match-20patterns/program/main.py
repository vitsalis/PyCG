
import ext
def f(): pass
def g(): pass
class Point:
    __match_args__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y
    @property
    def both(self):
        return (self.x, self.y)
class Later(Point):
    pass
Later.__match_args__ = ("y", "x")
class Items:
    def __getitem__(self, key):
        return g
    def __len__(self):
        return 2
def run(value):
    match value:
        case Point(first, second, both=[left, right]) | Later(second, first):
            first()
            left()
        case [head, *tail] if head:
            tail[0]()
        case {"key": handler, **rest}:
            handler()
            rest["other"]()
run(Point(f, g))
run(Later(g, f))
run(Items())
run({"key": f, "other": g})
