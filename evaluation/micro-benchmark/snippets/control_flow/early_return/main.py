def func1():
    pass

def run(skip):
    if skip:
        return
    func1()

run(True)
