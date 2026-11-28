
import typing
import kinds
if typing.TYPE_CHECKING:
    from kinds import KindT, Kind
def build(kind: "type[Kind]", items: "dict[str, KindT]") -> None:
    kind.make()
    items["a"].run()
class Record(typing.NamedTuple):
    kind: "KindT"
    def go(self):
        self.kind.run()
