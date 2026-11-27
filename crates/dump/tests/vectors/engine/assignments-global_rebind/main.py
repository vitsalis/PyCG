def func1():
    pass

def func2():
    pass

handler = func1

def install():
    global handler
    handler = func2

install()
handler()
