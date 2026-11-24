class C:
    def func(self):
        pass

class B:
    def __init__(self, c):
        self.c = c

    def func(self):
        self.c.func()

class A:
    def __init__(self):
        self.c = C()

    def func(self):
        b = B(self.c)
        b.func()

a = A()
a.func()
