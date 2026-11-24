from ext import Cls

def fn(a):
    a()

a = Cls()

fn(a.fun)
