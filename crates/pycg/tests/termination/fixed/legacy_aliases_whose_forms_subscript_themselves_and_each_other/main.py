from typing import List, TypeAlias, TypeVar
T = TypeVar('T')
A = List[T]
A = A[T]
B: TypeAlias = A[T]
A = B[T]
class C:
    D = List[T]
    D = D[T]
    def f(self, x: D[int]): pass
def f(x: A[int], y: B[int]): pass
