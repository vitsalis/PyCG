
import dataclasses
def f(): pass
class Named:
    def __set_name__(self, owner, name): pass
    def __get__(self, obj, owner=None): return f
@dataclasses.dataclass
class Point:
    x: int = 0
    named = Named()
def use(p):
    p.x
    p.named()
    p.y = p.x
    return p.y
for p in (Point(), Point()):
    use(p)
