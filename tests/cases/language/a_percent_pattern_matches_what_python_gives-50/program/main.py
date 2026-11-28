
def f(): pass
def g(): pass
table = {'_65   ': f, "zz_other": g}
table['_%(a(b)c)-05lr' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
