class MyClass:
    def func2(self):
        pass

    def func1(self):
        return self.func2

a = MyClass()
b = a.func1()
b()
