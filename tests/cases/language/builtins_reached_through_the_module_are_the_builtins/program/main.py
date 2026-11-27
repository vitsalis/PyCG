
import ext
def f(): pass
def g(): pass

import builtins
import builtins as b
from builtins import getattr as get
class Handler:
    def run(self): pass
def through_import():
    get(Handler(), "run")()
def through_module():
    builtins.getattr(Handler(), "run")()
    b.len([])
