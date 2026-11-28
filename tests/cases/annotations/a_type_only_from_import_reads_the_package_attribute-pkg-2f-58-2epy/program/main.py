
import pkg
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import X
def use(value: "X"):
    value.run()
