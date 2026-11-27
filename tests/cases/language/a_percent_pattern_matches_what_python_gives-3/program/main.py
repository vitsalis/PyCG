
def f(): pass
def g(): pass
table = {'_tail65': f, "zz_other": g}
table['_tail%((x))s' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
