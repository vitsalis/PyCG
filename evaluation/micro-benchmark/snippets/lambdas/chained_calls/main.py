def func3(a):
    a(1)

def func2(a, b):
    a(1)
    func3(b)

def func1(a, b, c):
    a(1)
    func2(b, c)

func1(lambda x: x + 1, lambda x: x + 2, lambda x: x + 3)
