class MyClass:
    def func3(self):
        pass

    def func2(self, a):
        a()

    def func1(self, a, b):
        a(b)

a = MyClass()
a.func1(a.func2, a.func3)
