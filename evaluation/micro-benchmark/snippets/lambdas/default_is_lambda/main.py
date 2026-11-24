def func1():
    pass

run = lambda g=lambda: func1(): g()
run()
