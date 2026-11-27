class A:
    x = 1
    def m(self):
        return self
class B(A):
    __slots__ = 'p'
    y = x = 2
