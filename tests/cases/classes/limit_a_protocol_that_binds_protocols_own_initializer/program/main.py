
from typing import Protocol
class P(Protocol):
    __init__ = Protocol.__init__
    def run(self): pass
P().run()
