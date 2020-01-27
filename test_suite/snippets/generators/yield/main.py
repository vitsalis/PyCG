def func(n):
    num = 0
    while num < n:
        yield num
        num += 1

for i in func(100):
    pass
