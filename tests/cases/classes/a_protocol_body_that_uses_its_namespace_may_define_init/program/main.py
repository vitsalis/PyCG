
from typing import Protocol
class P(Protocol):
    locals()["__init__"] = lambda self: None
    def run(self): pass
class Q(P, Protocol):
    def go(self): pass
class Plain(Protocol):
    def stop(self): pass
P().run()
Q().go()
Plain().stop()
