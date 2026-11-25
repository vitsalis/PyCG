def func1():
    def dec(f):
        return f

    return dec

@func1()
def func2():
    pass

func2()
