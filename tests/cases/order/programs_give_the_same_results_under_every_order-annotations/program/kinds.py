
import typing
from dataclasses import dataclass as frozen_class
def use(x: "KindT", *more: "KindT", **named: "list[Kind]"):
    x.run()
    for each in more:
        each.run()
class Kind:
    def run(self): pass
    @classmethod
    def make(cls): pass
class Fast(Kind):
    def run(self): pass
KindT = Kind | typing.Callable[[], None]
Tree = typing.Union[Kind, list["Tree"]]
@frozen_class(frozen=True)
class Holder:
    kind: "KindT"
    tree: Tree
    def go(self):
        self.kind.run()
        self.tree.run()
