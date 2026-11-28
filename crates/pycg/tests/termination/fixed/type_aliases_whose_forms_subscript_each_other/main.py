type A[T] = B[T]
type B[T] = A[T]
def f(x: A[int], y: 'B[int]'): pass
