def func1():
    pass

def func2():
    pass

def func3():
    pass

def func4():
    pass

def func5():
    pass

def fail():
    raise ValueError("fail")

try:
    func1()
    fail()
    func2()
except ValueError:
    func3()
else:
    func4()
finally:
    func5()
