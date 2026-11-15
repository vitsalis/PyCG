def func1():
    pass

def func2():
    pass

def choose(command):
    match command:
        case "start":
            return func1
        case "stop":
            return func2

choose("stop")()
