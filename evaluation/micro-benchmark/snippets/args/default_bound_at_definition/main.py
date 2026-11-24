def func1():
    pass

def func2():
    pass

handler = func1

def run(f=handler):
    f()

handler = func2
run()
