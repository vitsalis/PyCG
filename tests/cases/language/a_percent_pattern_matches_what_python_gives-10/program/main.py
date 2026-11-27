
def f(): pass
def g(): pass
table = {'a65': f, "zz_other": g}
table['a%(a(b)c)s' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
