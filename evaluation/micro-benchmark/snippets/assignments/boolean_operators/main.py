def func1():
    pass

def func2():
    pass

def func3():
    pass

def func4():
    pass

first = None or func1
first()

second = func2 and func3
second()

third = func4 or func2
third()
