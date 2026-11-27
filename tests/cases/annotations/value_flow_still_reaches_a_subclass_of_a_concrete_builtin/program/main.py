
import typing
class Names(list):
    def __iter__(self): return iter([])
def drain(xs: typing.Iterable[str]):
    for x in xs:
        pass
drain(Names())
