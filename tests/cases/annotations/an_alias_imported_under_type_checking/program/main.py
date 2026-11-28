
import typing
import strategies
if typing.TYPE_CHECKING:
    from strategies import BaseT
def run(s: "BaseT"):
    s(1)
