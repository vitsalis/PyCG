def func1():
    pass

def func2():
    pass

def make():
    current = func1

    def swap():
        nonlocal current
        current = func2

    def call():
        current()

    return swap, call

swap, call = make()
swap()
call()
