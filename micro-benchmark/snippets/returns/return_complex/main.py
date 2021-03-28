def func():
    return 1 + 1

func()


def func2():
    return 1

def func3():
    return func2

def func4(a):
    return func3()

func4()()

def func5():
    return func2() + 1

func5()
