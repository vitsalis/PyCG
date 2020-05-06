class MyClass:
    def __init__(self):
        pass

    def func1(self):
        pass

    def func2(self):
        pass

    def func3(self):
        pass

class MyClass2:
    def __init__(self):
        pass

a, b = MyClass(), MyClass2()

c, (d, e) = a.func1, (a.func2, a.func3)

c()
d()
e()
