def func1():
    pass

def func2():
    pass

def run():
    try:
        return func1()
    finally:
        func2()

run()
