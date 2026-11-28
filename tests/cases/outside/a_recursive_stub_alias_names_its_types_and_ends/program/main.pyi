
from shapes import Square
Tree = Square | tuple[Tree, ...]
A = B | None
B = A | None
def walk(tree: Tree) -> None: ...
def loop(x: A) -> None: ...
