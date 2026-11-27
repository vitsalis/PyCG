
def myopen(*args): pass
def setup():
    global open
    open = myopen
def use():
    open("x")
