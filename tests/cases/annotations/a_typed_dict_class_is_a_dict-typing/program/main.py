
import typing
class Parameters(typing.TypedDict, total=False):
    size: int
class Sized(Parameters):
    name: str
def make():
    return Parameters(size=1)
def use(params: Sized):
    params.get("size")
make().items()
Sized(size=2, name="a")
