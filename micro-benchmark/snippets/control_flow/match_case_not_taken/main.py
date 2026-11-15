def func1():
    pass

def func2():
    pass

def func3():
    pass

command = "stop"
match command:
    case "go":
        func1()
    case "stop":
        func2()
    case _:
        func3()
