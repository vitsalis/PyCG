def func1():
    pass

def func2():
    pass

verbose = True
handler = func1 if verbose else func2
handler()
