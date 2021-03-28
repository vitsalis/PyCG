def func2():
    pass

def func(key='a'):
    d[key] = func2

d = {}

func()
d['a']()
