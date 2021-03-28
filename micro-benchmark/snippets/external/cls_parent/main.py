from ext import parent

class A(parent):
    def fn(self):
        self.parent_fn()

a = A()
a.fn()
