def dec(f):
    def inner():
        f()

    return inner

@dec
def func():
    pass

def func2():
    func()

func2()
