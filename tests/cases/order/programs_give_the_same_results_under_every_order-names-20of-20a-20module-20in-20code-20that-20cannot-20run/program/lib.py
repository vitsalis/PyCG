
from typing import TYPE_CHECKING
def actual(): pass
def __getattr__(name):
    return actual
if False:
    def absent(): pass
if TYPE_CHECKING:
    from typing import Sequence
