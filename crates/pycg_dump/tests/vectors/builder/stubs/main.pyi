from typing import Any, List
import os.path as p
Alias = List[int]
class Base: ...
class C(Base[int], p.Mixin):
    attr: 'Alias'
    def m(self, a: int, b: p.Thing = ...) -> None: ...
def g(x: C, *rest: Alias, **kw: str) -> None: ...
h = g
v: List['C']
w: str
if flag:
    z: Base
else:
    y: 'C | None'
