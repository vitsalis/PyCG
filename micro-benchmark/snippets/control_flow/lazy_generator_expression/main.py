def func1():
    pass

def source():
    return [func1]

pending = (f() for f in source())
