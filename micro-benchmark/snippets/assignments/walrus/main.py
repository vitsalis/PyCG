def func1():
    pass

def pick():
    return func1

if (f := pick()) is not None:
    f()
