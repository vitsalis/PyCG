def func1():
    pass

def func2():
    pass

pair = (lambda: func1(), lambda: func2())
pair[1]()
