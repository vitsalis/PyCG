
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

import typing
from typing import Callable, Optional, Union
def optional(s: Optional[Strategy]):
    s(1)
def pipe(s: Strategy | None):
    s(1)
def union(s: Union[Strategy, Callable[[int], None]]):
    s(1)
def qualified(s: typing.Optional[typing.Union[int, Strategy]]):
    s(1)
