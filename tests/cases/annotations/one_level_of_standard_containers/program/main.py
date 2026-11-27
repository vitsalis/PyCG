
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

from collections.abc import Iterable, Sequence
from typing import Dict, List
def each(items: list[Strategy]):
    for s in items:
        s(1)
def old_list(items: List[Strategy]):
    items[0](1)
def sequence(items: Sequence[Strategy]):
    items[0](1)
def iterable(items: Iterable[Strategy]):
    for s in items:
        s(1)
def pairs(items: tuple[Strategy, ...]):
    first, second = items
    first(1)
def mapping(table: dict[str, Strategy]):
    table["x"](1)
def old_mapping(table: Dict[str, Strategy]):
    for s in table.values():
        s(1)
def deeper(items: list[list[Strategy]]):
    for inner in items:
        for s in inner:
            s(1)
