def nested_func():
    pass

def param_func(a):
    a()

def func(a):
    a(nested_func)

b = param_func
c = func
c(b)
