def func1():
    pass

def func2():
    pass

handlers = [func1]
alias = handlers
alias.append(func2)
handlers[1]()
