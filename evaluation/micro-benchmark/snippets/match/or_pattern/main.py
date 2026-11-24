def func1():
    pass

def func2():
    pass

match (func1, func2):
    case [handler] | [_, handler]:
        handler()
