class A:
    def func1(self):
        pass

class B(A):
    def func2(self):
        return self.func1

b = B()
fn = b.func2()
fn()
