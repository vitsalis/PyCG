
import typing
class Holder:
    def __init__(self, given):
        self.items: "list[KindT]" = list(given)
        self.kind: type[Kind] = given
    def go(self):
        for item in self.items:
            item.run()
        self.kind.make()
        current.run()
def base():
    return BASE
class Kind(base()):
    def __getitem__(self, index): pass
    def __len__(self): return 0
    def run(self): pass
    @classmethod
    def make(cls): pass
class Fast(Kind):
    def run(self): pass
KindT = Kind | None
BASE = typing.Sequence
current: typing.Optional[typing.Sequence[int]] = None
