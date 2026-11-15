def func1():
    pass

def wrap(f):
    def wrapper():
        f()
    return wrapper

wrapped = wrap(wrap(func1))
wrapped()
