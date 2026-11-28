
from typing import TYPE_CHECKING
from pkg.X import T
if TYPE_CHECKING:
    from pkg.X import T as AnnoT
def use(x: "AnnoT"):
    x.run()
use(T())
