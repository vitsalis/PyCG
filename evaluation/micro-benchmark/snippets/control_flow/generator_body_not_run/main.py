def func1():
    pass

def gen():
    func1()
    yield

g = gen()
