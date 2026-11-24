class A:
    def __init__(self):
        pass

    def func(self):
        pass

class B(A):
    pass

class C(A):
    def func(self):
        pass

class D(B, C):
    pass

d = D()
d.func()
