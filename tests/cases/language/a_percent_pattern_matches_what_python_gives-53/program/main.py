
def f(): pass
def g(): pass
table = {'_65': f, "zz_other": g}
table['_%(k)-0Ls' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
