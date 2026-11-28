
import typing
class Base:
    def __call__(self, state): pass
class Fast(Base):
    def __call__(self, state): pass
BaseT = Base | typing.Callable[[int], bool]
