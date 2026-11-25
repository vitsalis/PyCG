def func1():
    pass

def func2():
    pass

def outer():
    f = func1

    def inner():
        f()

    f = func2
    return inner

outer()()
