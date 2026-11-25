def func1():
    pass

def func2():
    pass

run = lambda f=func1: f()
run(func2)
