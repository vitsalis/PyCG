
def f(): pass
def g(): pass
def h(): pass

from typing import TYPE_CHECKING
class Base:
    def run(self):
        f()
class Child(Base):
    if TYPE_CHECKING:
        def run(self): ...
    temporary = g
    del temporary
def use():
    Child().run()
    Child.temporary()
