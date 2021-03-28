def func1(key='a'):
    d[key]()

def func2():
    pass

def func3():
    pass

d = {
    "a": func2,
    'b': func3
}

func1()
func1('b')
