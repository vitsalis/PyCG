
class Base:
    @staticmethod
    def make(): pass
class Left(Base): pass
class Right(Base): pass
class Both(Left, Right):
    @staticmethod
    def make(): pass
def late():
    return Both
class Later(late()):
    @staticmethod
    def make(): pass
def build(kind: type[Base]):
    kind.make()
