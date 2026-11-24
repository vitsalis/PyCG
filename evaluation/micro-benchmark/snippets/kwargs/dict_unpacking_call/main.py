def func1():
    pass

def func2():
    pass

def run(f, g):
    f()

options = {"g": func2, "f": func1}
run(**options)
