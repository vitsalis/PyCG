def func1():
    pass

def func2():
    pass

def call_first(first, second):
    first()

pair = [func1, func2]
call_first(*pair)
