
import pkg
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import X
    import pkg.X
def use(x: "X.T", y: "pkg.X.T"):
    x.run()
    y.run()
