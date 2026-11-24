def dec1(f):
    return f

def dec2(f):
    return f

a = dec1
a = dec2

@a
def func():
    pass

func()
