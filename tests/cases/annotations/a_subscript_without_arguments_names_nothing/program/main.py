
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

from typing import Annotated, Type
def run(first: Annotated[()], second: Type[()]):
    first(1)
    second(1)
