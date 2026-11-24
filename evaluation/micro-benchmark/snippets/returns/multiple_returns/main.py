def func1():
    pass

def func2():
    pass

def pick(first):
    if first:
        return func1
    return func2

pick(False)()
