
import dataclasses
from dataclasses import dataclass
@dataclass
class Point:
    def norm(self): pass
@dataclasses.dataclass(frozen=True)
class Line:
    def length(self): pass
def use(p, q):
    Point().norm()
    Line().length()
