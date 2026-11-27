import sys
from .mod import C, helper as run
from . import mod
if sys.argv:
    from .mod import helper as either
else:
    from .other import helper as either
from requests import get
