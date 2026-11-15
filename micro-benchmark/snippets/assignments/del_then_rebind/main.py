def func1():
    pass

def func2():
    pass

handler = func1
del handler
handler = func2
handler()
