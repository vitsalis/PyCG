def func2():
    pass

def func1(n):
    num = 0
    while num < n:
        yield func2
        num += 1

for i in func1(100):
    i()
