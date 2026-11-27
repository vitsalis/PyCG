
from typing import Protocol
class Sized(Protocol):
    def __init__(self): pass
class Proto(Protocol):
    def run(self): pass
class Box(Sized):
    def __init__(self): pass
Sized()
Proto().run()
Box()
