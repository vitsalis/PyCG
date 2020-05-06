def func3(a):
    a()

def func2(a, b):
    a()
    func3(b)

def func1(a, b, c):
    a()
    func2(b, c)

func1(lambda x: x + 1, lambda x: x + 2, lambda x: x + 3)
