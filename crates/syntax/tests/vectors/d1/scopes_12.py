
a = lambda: 1
def f():
    b = lambda: 2
    c = (lambda: 3)(lambda: 4)
d = [lambda: 5 for _ in range(2)]
e = lambda: lambda: 6
