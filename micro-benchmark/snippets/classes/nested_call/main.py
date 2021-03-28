class MyClass:
    def func(self):
        def nested():
            pass

        nested()

a = MyClass()
a.func()
