class MyClass:
    def func1(self):
        pass

    def func2(self):
        a = self
        a.func1()

a = MyClass()
a.func2()
