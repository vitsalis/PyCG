def func1():
    pass

def func2():
    pass

def call_second(*funcs):
    funcs[1]()

call_second(func1, func2)
