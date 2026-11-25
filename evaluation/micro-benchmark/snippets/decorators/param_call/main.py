def dec(f):
    f()
    return f

@dec
def func():
    pass

func()
