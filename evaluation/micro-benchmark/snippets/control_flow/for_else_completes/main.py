def func1():
    pass

def func2():
    pass

for f in (func1,):
    f()
else:
    func2()
