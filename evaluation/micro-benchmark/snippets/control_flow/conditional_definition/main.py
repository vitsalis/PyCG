def func1():
    pass

def func2():
    pass

fast = True
if fast:
    def handler():
        func1()
else:
    def handler():
        func2()

handler()
