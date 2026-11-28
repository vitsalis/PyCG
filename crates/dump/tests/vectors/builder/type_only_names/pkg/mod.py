import typing
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import Sequence as Seq
    from .models import Model
    import os.path
    import xml.etree as tree
    if typing.TYPE_CHECKING:
        from json import loads
else:
    from json import dumps
if not TYPE_CHECKING:
    pass
else:
    from .base import Base
class C:
    if typing.TYPE_CHECKING:
        from .other import Other
    other: Other
def uses(seq: Seq, model: Model, path: os.path, etree: tree, load: loads,
         base: Base, dump: dumps) -> None:
    pass
