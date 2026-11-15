def func1():
    pass

def func2():
    pass

def call_all(*funcs):
    for f in funcs:
        f()

call_all(func1, func2)
