class B:
    def funcb(self):
        self.smth = self.func

    def func(self):
        pass

class A(B):
    def funca(self):
        self.smth = self.func

    def func(self):
        pass

a = A()
a.funcb()
a.smth()

a.funca()
a.smth()
