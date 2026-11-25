class Vector:
    def __add__(self, other):
        return self

    def __sub__(self, other):
        return self

    def __matmul__(self, other):
        return 0


v = Vector()
w = v + v
d = v @ w
