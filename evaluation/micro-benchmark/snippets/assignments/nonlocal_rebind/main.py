def func1():
    pass

def func2():
    pass

def outer():
    handler = func1

    def install():
        nonlocal handler
        handler = func2

    install()
    handler()

outer()
