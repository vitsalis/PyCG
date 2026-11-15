def func1():
    pass

def func2():
    pass

def func3():
    pass

def func4():
    pass

def run(a, b, c, d):
    b()
    d()

run(*[func1], *(func2,), **{"c": func3}, **{"d": func4})
