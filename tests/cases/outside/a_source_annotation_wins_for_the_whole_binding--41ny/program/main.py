class Wrong:
    def ping(self): pass
flag = input()
from typing import Any
x: Any
x = None
x.ping()
class C:
    from typing import Any
    x: Any
    x = None
    def go(self):
        self.x.ping()
