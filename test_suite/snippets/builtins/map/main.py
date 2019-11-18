def func(x):
    pass

map([1, 2, 3], func)

def func2(x):
    return func(x)

map([1, 2, 3], func2)

def func3(x):
    def func():
        return x
    return func

res = map([1, 2, 3], func3)

for r in res:
    r()
