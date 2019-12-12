class A:
    def __init__(self):
        self.smth = self.func2

    def func(self):
        self.smth()

    def func2(self):
        pass

a = A()
a.func()
