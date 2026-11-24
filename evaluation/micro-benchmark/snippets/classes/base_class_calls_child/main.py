class A:
    def func(self):
        self.child()

class B(A):
    def __init__(self):
        self.child = self.func2

    def func2(self):
        pass

class C(A):
    def __init__(self):
        self.child = self.func2

    def func2(self):
        pass

b = B()
b.func()

c = C()
c.func()
