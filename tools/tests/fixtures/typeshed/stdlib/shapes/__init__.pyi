import sys
from ._impl import *
from ._impl import _Hidden as Hidden
from ._impl import Circle as Ball
from typing import Any

__all__ = ["Shape", "area", "Hidden", "Ball"]
if sys.version_info >= (3, 13):
    __all__ += ["scale"]
