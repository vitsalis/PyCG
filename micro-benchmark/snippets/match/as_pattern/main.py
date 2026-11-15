def func1():
    pass

def func2():
    pass

match [func1, func2]:
    case [_, _] as pair:
        pair[0]()
