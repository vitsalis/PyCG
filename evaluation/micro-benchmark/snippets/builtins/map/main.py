def func(x):
    pass

list(map(func, [1, 2, 3]))

def func2(x):
    return func(x)

list(map(func2, [1, 2, 3]))

def func3(x):
    def func():
        return x
    return func

res = map(func3, [1, 2, 3])

for r in res:
    r()
