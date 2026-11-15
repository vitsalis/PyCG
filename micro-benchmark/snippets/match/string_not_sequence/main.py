def func1():
    pass

def func2():
    pass

def classify(subject):
    match subject:
        case [first, second]:
            return func1
        case _:
            return func2

classify("ab")()
