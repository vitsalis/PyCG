def default():
    pass

def func1():
    pass

def inner(callback=default):
    callback()

def outer(**kwargs):
    inner(**kwargs)

outer(callback=func1)
