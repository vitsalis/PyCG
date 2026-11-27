
x = 1
def f():
    nonlocal x
    x = 2
def outer():
    def inner():
        nonlocal y
        y = 2
