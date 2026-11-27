
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

import types
from typing import Any, Callable, TypeVar
T = TypeVar("T", bound=Strategy)
def f(a: object, b: Any, c: Callable, d: T, e: int, g: types.ModuleType, h: type):
    a(1)
    b(1)
    c(1)
    d(1)
    e(1)
    g(1)
    h(1)
