def func1():
    pass

def func2():
    pass

def run(**handlers):
    handlers["second"]()

run(first=func1, second=func2)
