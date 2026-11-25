class A:
    def func(self):
        pass

class B:
    def __init__(self, a):
        self.a = a

    def func(self):
        self.a.func()

a = A()

b = B(a)

b.func()
