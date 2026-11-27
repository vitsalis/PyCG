
import pkg.kinds
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import kinds
    import pkg.kinds as aliased
def use(value: "kinds.Kind", other: "aliased.Kind"):
    value.run()
    other.run()
