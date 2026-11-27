
from typing import TYPE_CHECKING
def actual(): pass
class Base:
    def inherited(self): pass
class Proxy(Base):
    def __getattr__(self, name):
        return actual
    if TYPE_CHECKING:
        def method(self): ...
    if False:
        def inherited(self): ...
