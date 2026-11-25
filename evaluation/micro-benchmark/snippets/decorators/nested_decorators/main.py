def dec1(f):
    def inner():
        return f()
    return inner

def dec2(f):
    def inner():
        return f()

    return inner

@dec1
@dec2
def func():
    pass

func()
