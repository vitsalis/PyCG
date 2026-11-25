def func1():
    pass

def func2():
    pass

handlers = [func1]
alias = handlers
alias += [func2]
handlers[1]()
