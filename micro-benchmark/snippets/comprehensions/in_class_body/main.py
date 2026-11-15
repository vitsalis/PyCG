def func1():
    return 1

def func2():
    return 2

class Config:
    handlers = (func1, func2)
    results = [h() for h in handlers]
