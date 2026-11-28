import sys
from ._impl import *
from ._impl import _Hidden as Hidden
from typing import Any

__all__ = ["Shape", "area", "Hidden"]
if sys.version_info >= (3, 13):
    __all__ += ["scale"]
