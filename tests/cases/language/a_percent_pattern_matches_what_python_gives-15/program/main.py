
def f(): pass
def g(): pass
table = {'65': f, "zz_other": g}
table['%(k)s' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
