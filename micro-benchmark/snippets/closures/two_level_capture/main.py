def func1():
    pass

def outer(f):
    def middle():
        def inner():
            f()
        return inner
    return middle

outer(func1)()()
