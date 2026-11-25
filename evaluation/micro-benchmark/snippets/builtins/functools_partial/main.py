import functools

def greet(greeting, name):
    pass

def farewell(name):
    pass

hello = functools.partial(greet, "hello")
hello("ann")
