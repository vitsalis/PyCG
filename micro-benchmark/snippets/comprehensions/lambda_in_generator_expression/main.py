def func1():
    pass

def func2():
    pass

first = lambda: func1()
gen = (lambda: func2() for _ in range(1))
second = next(gen)
second()
first()
