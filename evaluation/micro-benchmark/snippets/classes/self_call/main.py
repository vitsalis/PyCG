class MyClass:
    def __init__(self):
        self.func1()

    def func1(self):
        pass

    def func2(self):
        self.func1()

a = MyClass()

a.func2()
