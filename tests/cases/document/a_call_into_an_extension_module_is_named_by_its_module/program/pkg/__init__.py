from . import _speedups
from ._fast import escape
from .both import g
import pkg._abi
def f():
    _speedups.run()
    escape()
    pkg._abi.go()
    g()
