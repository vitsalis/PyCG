
from typing import TYPE_CHECKING
import strategies
import pkg.kinds
if TYPE_CHECKING:
    from strategies import BaseT
    import pkg.kinds as kinds
    from pkg import kinds as other
def run(s: "BaseT"):
    s(1)
def make(k: "kinds.Kind", o: "other.Kind"):
    k.run()
    o.run()
class Holder:
    if TYPE_CHECKING:
        from strategies import Fast
    def go(self, f: "Fast"):
        f(1)
