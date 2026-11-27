
from typing import Sequence
class Meta(type):
    def describe(cls): pass
class Base(metaclass=Meta):
    def __init__(self): pass
    def copy(self):
        return type(self)()
class Child(Base):
    def __init__(self): pass
def late():
    return Child()
def run(fields: Sequence[Base | type[Base]], name="x"):
    type(late()).describe()
    type(name)().upper()
    type(name, (Base,), {})()
    for field in fields:
        type(field)()
late().copy()
