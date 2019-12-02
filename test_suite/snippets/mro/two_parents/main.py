class A:
    def func(self):
        pass

class B:
    def __init__(self):
        pass

    def func(self):
        pass

class C(A, B):
    pass

c = C()
c.func()
