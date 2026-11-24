def func1():
    pass

def func2():
    pass

def run(*, first, second):
    second()

run(second=func2, first=func1)
