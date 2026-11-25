def func1():
    pass

def func2():
    pass

def run(f, /, **kwargs):
    f()
    kwargs["f"]()

run(func1, f=func2)
