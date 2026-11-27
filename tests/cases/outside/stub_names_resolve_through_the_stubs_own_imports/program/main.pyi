
from __future__ import annotations
import collections.abc
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING
from shapes import Shape
if TYPE_CHECKING:
    from shapes import Square
class Local: ...
def report(
    shape: Shape,
    many: Sequence[Square],
    more: collections.abc.Sequence["Square"],
    square: Square,
    local: Local,
    path: Path,
) -> None: ...
