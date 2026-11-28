
def f(): pass
def g(): pass
table = {'     ': f, "zz_other": g}
table['%(a(b)c)5.a' % {'k': 65, 'a(b)c': 65, '(x)': 65}]()
