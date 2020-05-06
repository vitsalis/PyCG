def dec(f):
    return f

def func():
    def dec(f):
        return f

    @dec
    def inner():
        pass

func()
