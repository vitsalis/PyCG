def return_func():
    pass

def func():
    a = return_func
    return a

a = func
a()()
