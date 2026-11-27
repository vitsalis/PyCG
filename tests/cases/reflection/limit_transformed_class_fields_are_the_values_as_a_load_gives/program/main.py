
import enum
from dataclasses import dataclass
from typing import NamedTuple
def callback(): pass
class Fn:
    def __call__(self): pass
class T(NamedTuple):
    field: object = callback
@dataclass(slots=True)
class S:
    field: object = callback
class E(enum.Enum):
    A = Fn()
def direct():
    T.field()
    S.field()
    E.A()
def through_the_namespace():
    T.__dict__["field"]()
    S.__dict__["field"]()
    E.__dict__["A"]()
direct()
through_the_namespace()
