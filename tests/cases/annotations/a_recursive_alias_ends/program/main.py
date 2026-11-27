
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

from typing import Union
Tree = Union[Strategy, list["Tree"]]
def walk(tree: Tree):
    tree(1)
