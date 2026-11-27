
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import ns.a as sub
def use(x: "sub.b.T"):
    x.run()
