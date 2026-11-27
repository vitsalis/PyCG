
import typing
class Base:
    @classmethod
    def make(cls): pass
class Child(Base):
    @classmethod
    def make(cls): pass
def build(kind: type[Base]):
    kind.make()
def old_style(kind: typing.Type[Base]):
    kind.make()
