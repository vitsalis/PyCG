def func1():
    pass

def func2():
    pass

def func3():
    pass

handlers = [func1, func2]
i = 0
while i < 2:
    handlers[i]()
    if handlers[i] is func1:
        break
    i += 1
else:
    func3()
