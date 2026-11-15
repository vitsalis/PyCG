def func1():
    pass

make = lambda f: lambda: f()
make(func1)()
